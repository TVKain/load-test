import sse from 'k6/x/sse';
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Trend } from 'k6/metrics';

// =============================================================================
// Configuration
// =============================================================================
const CLOUDCIX_API_BASE = __ENV.CLOUDCIX_API_BASE;
const CLOUDCIX_API_USERNAME = __ENV.CLOUDCIX_API_USERNAME;
const CLOUDCIX_API_PASSWORD = __ENV.CLOUDCIX_API_PASSWORD;
const CLOUDCIX_API_KEY = __ENV.CLOUDCIX_API_KEY;
const CHATBOT_NAME = __ENV.CHATBOT_NAME;

if (!CLOUDCIX_API_BASE) throw new Error('CLOUDCIX_API_BASE is required');
if (!CLOUDCIX_API_USERNAME) throw new Error('CLOUDCIX_API_USERNAME is required');
if (!CLOUDCIX_API_PASSWORD) throw new Error('CLOUDCIX_API_PASSWORD is required');
if (!CLOUDCIX_API_KEY) throw new Error('CLOUDCIX_API_KEY is required');
if (!CHATBOT_NAME) throw new Error('CHATBOT_NAME is required');

const AUTH_URL = `https://membership.${CLOUDCIX_API_BASE}/auth/login/`;
const CONTACT_BASE = __ENV.CONTACT_BASE_URL || `https://contact.${CLOUDCIX_API_BASE}`;

const CONTACT_ID = 6885;
const FIRST_CHUNK_TIMEOUT_MS = parseInt(__ENV.FIRST_CHUNK_TIMEOUT_MS || '300000');

const PRESET = __ENV.PRESET || 'breaking';
let STAGES;

try {
    STAGES = JSON.parse(open(`./presets/${PRESET}.json`));
} catch (e) {
    throw new Error(`Unknown preset "${PRESET}" — make sure presets/${PRESET}.json exists`);
}

// =============================================================================
// Questions — loaded from questions/<QUESTIONS_FILE>.json (required)
// =============================================================================
const QUESTIONS_FILE = __ENV.QUESTIONS_FILE;
if (!QUESTIONS_FILE) {
    throw new Error('QUESTIONS_FILE is required — e.g. make run PRESET=soak QUESTIONS_FILE=sample');
}

const QUESTIONS_PATH = `./questions/${QUESTIONS_FILE}.json`;
let QUESTIONS;

try {
    QUESTIONS = JSON.parse(open(QUESTIONS_PATH));
    if (!Array.isArray(QUESTIONS) || QUESTIONS.length === 0) {
        throw new Error('Questions file must be a non-empty JSON array');
    }
} catch (e) {
    throw new Error(`Failed to load questions file "${QUESTIONS_PATH}": ${e.message}`);
}

// =============================================================================
// Metrics (all in ms)
// =============================================================================

// -- Conversation creation metrics --
const conv_total = new Counter('conv_total');
const conv_success = new Counter('conv_success');
const conv_failed = new Counter('conv_failed');

// -- Chat request metrics --
const chat_total = new Counter('chat_total');
const chat_success = new Counter('chat_success');
const chat_failed = new Counter('chat_failed');

// -- Timing metrics --
const ttft_ms = new Trend('ttft_ms', true);
const chunk_iat_ms = new Trend('chunk_inter_arrival_ms', true);

// =============================================================================
// VU state — persists across iterations for the lifetime of each VU
// =============================================================================
const vuState = { conversationId: null, token: null };

// =============================================================================
// Load Profile
// =============================================================================
export const options = {
    scenarios: {
        [PRESET]: {
            executor: 'ramping-vus',
            stages: STAGES,
            gracefulStop: '300s',
            gracefulRampDown: '300s',
        },
    },
    thresholds: {
        'ttft_ms': ['p(95)<5000'],
        'chunk_inter_arrival_ms': ['p(95)<1000'],
        'chat_failed': ['count<100'],
    },
};

// =============================================================================
// Setup — auth only
// =============================================================================
export function setup() {
    const authRes = http.post(AUTH_URL, JSON.stringify({
        email: CLOUDCIX_API_USERNAME,
        password: CLOUDCIX_API_PASSWORD,
        api_key: CLOUDCIX_API_KEY,
    }), { headers: { 'Content-Type': 'application/json' }, timeout: '10s' });

    check(authRes, { 'auth 201': (r) => r.status === 201 });
    if (authRes.status !== 201) {
        throw new Error(`Auth failed (${authRes.status}): ${authRes.body}`);
    }

    const token = authRes.json('token');
    console.log('Auth token acquired');
    console.log(`Chatbot: ${CHATBOT_NAME}`);
    console.log(`First chunk timeout: ${FIRST_CHUNK_TIMEOUT_MS}ms`);
    console.log(`Stages: ${JSON.stringify(STAGES)}`);
    console.log(`Questions pool: ${QUESTIONS.length} questions from ${QUESTIONS_PATH}`);
    return { token };
}

// =============================================================================
// Auth refresh — called when a 401 is received during the test
// =============================================================================
function refreshToken() {
    console.log(`[VU ${__VU}] 🔄 Token expired — re-authenticating...`);
    const authRes = http.post(AUTH_URL, JSON.stringify({
        email: CLOUDCIX_API_USERNAME,
        password: CLOUDCIX_API_PASSWORD,
        api_key: CLOUDCIX_API_KEY,
    }), { headers: { 'Content-Type': 'application/json' }, timeout: '10s' });

    if (authRes.status !== 201) {
        console.error(`[VU ${__VU}] ✗ Re-auth failed (${authRes.status}): ${authRes.body}`);
        return null;
    }

    const newToken = authRes.json('token');
    console.log(`[VU ${__VU}] ✓ Token refreshed`);
    return newToken;
}

// =============================================================================
// Default VU
// =============================================================================
export default function (data) {
    // Use per-VU token if refreshed, otherwise fall back to setup token
    if (!vuState.token) {
        vuState.token = data.token;
    }

    // ── Create conversation once per VU lifetime ─────────────────────────────
    if (vuState.conversationId === null) {
        conv_total.add(1);

        const convRes = http.post(
            `${CONTACT_BASE}/conversation/${CHATBOT_NAME}/`,
            JSON.stringify({
                contact_id: CONTACT_ID,
                name: `Load Test VU ${__VU}`,
            }),
            {
                headers: {
                    'Content-Type': 'application/json',
                    'X-Auth-Token': vuState.token,
                },
                timeout: '300s',
            }
        );

        // Refresh token if expired
        if (convRes.status === 401) {
            const newToken = refreshToken();
            if (!newToken) { sleep(1); return; }
            vuState.token = newToken;
            sleep(1);
            return; // retry next iteration with fresh token
        }

        const convOk = check(convRes, { 'conversation created 201': (r) => r.status === 201 });
        if (!convOk) {
            conv_failed.add(1);
            console.error(`[VU ${__VU}] ✗ Failed to create conversation — status=${convRes.status} body=${convRes.body}`);
            sleep(1);
            return;
        }

        conv_success.add(1);
        vuState.conversationId = convRes.json('content.id');
        console.log(`[VU ${__VU}] ✓ Conversation created: ${vuState.conversationId}`);
    }

    // ── Stream an answer ─────────────────────────────────────────────────────
    const question = QUESTIONS[Math.floor(Math.random() * QUESTIONS.length)];
    const startTime = Date.now();
    let firstChunkTime = null;
    let lastChunkTime = null;
    let chunkCount = 0;
    let timedOut = false;

    chat_total.add(1);

    const questionPreview = question.length > 128
        ? `${question.slice(0, 128)}... [${question.length} chars]`
        : question;
    console.log(`[VU ${__VU}] ⏳ Waiting for first chunk... (question: "${questionPreview}")`);

    const res = sse.open(
        `${CONTACT_BASE}/answer/${CHATBOT_NAME}/`,
        {
            method: 'POST',
            body: JSON.stringify({ question, conversation_id: vuState.conversationId }),
            headers: {
                'Content-Type': 'application/json',
                'X-Auth-Token': vuState.token,
                'Accept': '*/*',
            },
            timeout: `${FIRST_CHUNK_TIMEOUT_MS}ms`,
        },
        function (client) {
            client.on('event', function (event) {
                processChunk(event.data);
            });

            client.on('error', function (e) {
                const raw = e.error();
                if (raw.startsWith('unknown event:')) {
                    processChunk(raw.replace('unknown event:', '').trim());
                } else {
                    const elapsed = Date.now() - startTime;
                    if (firstChunkTime === null) {
                        timedOut = true;
                        console.error(`[VU ${__VU}] ✗ First chunk timeout — no chunk received after ${elapsed}ms`);
                    } else {
                        console.error(`[VU ${__VU}] ✗ Connection error after ${elapsed}ms: ${raw}`);
                    }
                }
            });

            function processChunk(chunk) {
                if (!chunk || chunk === '[DONE]') return;

                const now = Date.now();

                if (firstChunkTime === null) {
                    firstChunkTime = now;
                    ttft_ms.add(now - startTime);
                    console.log(`[VU ${__VU}] ✓ First chunk received after ${now - startTime}ms: "${chunk}"`);
                }

                if (lastChunkTime !== null) {
                    chunk_iat_ms.add(now - lastChunkTime);
                }

                lastChunkTime = now;
                chunkCount++;
            }
        }
    );

    const ok = check(res, { 'status 200': (r) => r.status === 200 });

    if (res.status === 401) {
        // Token expired — refresh silently, do not count as a failure
        const newToken = refreshToken();
        if (newToken) vuState.token = newToken;
        console.warn(`[VU ${__VU}] 🔄 401 Unauthorized — token refreshed, retrying next iteration`);
        sleep(1);
        return;
    } else if (ok && chunkCount > 0 && !timedOut) {
        chat_success.add(1);
    } else {
        chat_failed.add(1);
        if (res.status === 502) {
            console.warn(`[VU ${__VU}] ✗ 502 Bad Gateway — server overloaded`);
        } else if (timedOut) {
            console.error(`[VU ${__VU}] ✗ Failed — first chunk timeout after ${FIRST_CHUNK_TIMEOUT_MS}ms`);
        } else if (res.status === 0) {
            console.error(`[VU ${__VU}] ✗ Failed — no response after ${Date.now() - startTime}ms`);
        } else if (res.status === 200 && chunkCount === 0) {
            console.warn(`[VU ${__VU}] ✗ Failed — stream opened successfully but server returned no chunks (empty response)`);
        } else {
            console.warn(`[VU ${__VU}] ✗ Failed — status=${res.status} chunks=${chunkCount}`);
        }
    }

    sleep(Math.random() * 2 + 0.5);
}

// =============================================================================
// Summary
// =============================================================================
export function handleSummary(data) {
    const convTotal = data.metrics.conv_total ? data.metrics.conv_total.values.count : 0;
    const convSuccess = data.metrics.conv_success ? data.metrics.conv_success.values.count : 0;
    const convFailed = data.metrics.conv_failed ? data.metrics.conv_failed.values.count : 0;
    const chatTotal = data.metrics.chat_total ? data.metrics.chat_total.values.count : 0;
    const chatSuccess = data.metrics.chat_success ? data.metrics.chat_success.values.count : 0;
    const chatFailed = data.metrics.chat_failed ? data.metrics.chat_failed.values.count : 0;
    const interrupted = chatTotal - chatSuccess - chatFailed;

    const ttft = data.metrics.ttft_ms;
    const iat = data.metrics.chunk_inter_arrival_ms;

    const summary = `
─── Benchmark Summary ──────────────────────────
  Chatbot:     ${CHATBOT_NAME}
  Stages:      ${JSON.stringify(STAGES)}

  Conversations
    Total:       ${convTotal}
    Success:     ${convSuccess}
    Failed:      ${convFailed}

  Chat Requests
    Total:       ${chatTotal}
    Success:     ${chatSuccess}
    Failed:      ${chatFailed}
    Interrupted: ${interrupted}

  TTFT
    min:         ${ttft ? (ttft.values.min).toFixed(2) : 'N/A'}ms
    p(99):       ${ttft ? (ttft.values['p(99)']).toFixed(2) : 'N/A'}ms
    max:         ${ttft ? (ttft.values.max).toFixed(2) : 'N/A'}ms

  Chunk Inter-Arrival
    min:         ${iat ? (iat.values.min).toFixed(2) : 'N/A'}ms
    p(99):       ${iat ? (iat.values['p(99)']).toFixed(2) : 'N/A'}ms
    max:         ${iat ? (iat.values.max).toFixed(2) : 'N/A'}ms
────────────────────────────────────────────────
`;

    console.log(summary);
    return {};
}

// =============================================================================
// Teardown
// =============================================================================
export function teardown(data) {
    console.log('─── Benchmark complete ───');
    console.log(`Chatbot: ${CHATBOT_NAME}`);
}