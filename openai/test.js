import sse from 'k6/x/sse';
import { check, sleep } from 'k6';
import { Counter, Trend } from 'k6/metrics';

// =============================================================================
// Configuration
// =============================================================================
const OPENAI_BASE_URL = __ENV.OPENAI_BASE_URL;
const OPENAI_API_KEY = __ENV.OPENAI_API_KEY;
const OPENAI_MODEL = __ENV.OPENAI_MODEL;
const OPENAI_TEMPERATURE = parseFloat(__ENV.OPENAI_TEMPERATURE || '0');
const OPENAI_TOP_P = parseFloat(__ENV.OPENAI_TOP_P || '1');
const OPENAI_SEED_RAW = __ENV.OPENAI_SEED;
const OPENAI_SEED = OPENAI_SEED_RAW !== undefined && OPENAI_SEED_RAW !== ''
    ? parseInt(OPENAI_SEED_RAW, 10)
    : null;
const OPENAI_SLEEP_MIN = parseFloat(__ENV.OPENAI_SLEEP_MIN || '0.5');
const OPENAI_SLEEP_MAX = parseFloat(__ENV.OPENAI_SLEEP_MAX || '2.5');

if (!OPENAI_BASE_URL) throw new Error('OPENAI_BASE_URL is required (e.g. http://localhost:8000/v1)');
if (!OPENAI_API_KEY) throw new Error('OPENAI_API_KEY is required');
if (!OPENAI_MODEL) throw new Error('OPENAI_MODEL is required');
if (Number.isNaN(OPENAI_TEMPERATURE) || OPENAI_TEMPERATURE < 0 || OPENAI_TEMPERATURE > 2) {
    throw new Error('OPENAI_TEMPERATURE must be a number between 0 and 2');
}
if (Number.isNaN(OPENAI_TOP_P) || OPENAI_TOP_P <= 0 || OPENAI_TOP_P > 1) {
    throw new Error('OPENAI_TOP_P must be a number > 0 and <= 1');
}
if (OPENAI_SEED_RAW !== undefined && OPENAI_SEED_RAW !== '' && Number.isNaN(OPENAI_SEED)) {
    throw new Error('OPENAI_SEED must be an integer when provided');
}
if (Number.isNaN(OPENAI_SLEEP_MIN) || OPENAI_SLEEP_MIN < 0) {
    throw new Error('OPENAI_SLEEP_MIN must be a non-negative number');
}
if (Number.isNaN(OPENAI_SLEEP_MAX) || OPENAI_SLEEP_MAX < 0) {
    throw new Error('OPENAI_SLEEP_MAX must be a non-negative number');
}
if (OPENAI_SLEEP_MIN > OPENAI_SLEEP_MAX) {
    throw new Error('OPENAI_SLEEP_MIN must be <= OPENAI_SLEEP_MAX');
}

const FIRST_CHUNK_TIMEOUT_MS = parseInt(__ENV.FIRST_CHUNK_TIMEOUT_MS || '300000');
const COMPLETIONS_URL = `${OPENAI_BASE_URL.replace(/\/+$/, '')}/chat/completions`;

const PRESET = __ENV.PRESET || 'breaking';
let STAGES;

try {
    STAGES = JSON.parse(open(`../shared/presets/${PRESET}.json`));
} catch (e) {
    throw new Error(`Unknown preset "${PRESET}" — make sure shared/presets/${PRESET}.json exists`);
}

// =============================================================================
// Questions — loaded from questions/<QUESTIONS_FILE>.json (required)
// =============================================================================
const QUESTIONS_FILE = __ENV.QUESTIONS_FILE;
if (!QUESTIONS_FILE) {
    throw new Error('QUESTIONS_FILE is required — e.g. make run SCRIPT=openai QUESTIONS_FILE=cloudcix');
}

const QUESTIONS_PATH = `questions/${QUESTIONS_FILE}.json`;
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

// -- Chat request metrics --
const chat_total = new Counter('chat_total');
const chat_success = new Counter('chat_success');
const chat_failed = new Counter('chat_failed');

// -- Timing metrics --
const ttft_ms = new Trend('ttft_ms', true);
const chunk_iat_ms = new Trend('chunk_inter_arrival_ms', true);

// -- Token metrics --
const tokens_per_request = new Trend('tokens_per_request', true);
const total_duration_ms = new Trend('total_duration_ms', true);

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
// Setup
// =============================================================================
export function setup() {
    console.log(`OpenAI Base URL: ${OPENAI_BASE_URL}`);
    console.log(`Model: ${OPENAI_MODEL}`);
    console.log(`Completions URL: ${COMPLETIONS_URL}`);
    console.log(`First chunk timeout: ${FIRST_CHUNK_TIMEOUT_MS}ms`);
    console.log(`Sampling: temperature=${OPENAI_TEMPERATURE}, top_p=${OPENAI_TOP_P}${OPENAI_SEED !== null ? `, seed=${OPENAI_SEED}` : ''}`);
    console.log(`Sleep between iterations: ${OPENAI_SLEEP_MIN}–${OPENAI_SLEEP_MAX}s`);
    console.log(`Stages: ${JSON.stringify(STAGES)}`);
    console.log(`Questions pool: ${QUESTIONS.length} questions from ${QUESTIONS_PATH}`);
    return {};
}

// =============================================================================
// Default VU
// =============================================================================
export default function () {
    const question = QUESTIONS[Math.floor(Math.random() * QUESTIONS.length)];
    let startTime = null;
    let firstChunkTime = null;
    let lastChunkTime = null;
    let chunkCount = 0;
    let timedOut = false;
    let lastContent = null;

    chat_total.add(1);

    const questionPreview = question.length > 128
        ? `${question.slice(0, 128)}... [${question.length} chars]`
        : question;
    console.log(`[VU ${__VU}] ⏳ Waiting for first chunk... (question: "${questionPreview}")`);

    const requestBody = {
        model: OPENAI_MODEL,
        messages: [{ role: 'user', content: question }],
        temperature: OPENAI_TEMPERATURE,
        top_p: OPENAI_TOP_P,
        n: 1,
        stream: true,
    };
    if (OPENAI_SEED !== null) {
        requestBody.seed = OPENAI_SEED;
    }
    const payload = JSON.stringify(requestBody);

    // Start timer right before making the HTTP request
    startTime = Date.now();
    
    const res = sse.open(
        COMPLETIONS_URL,
        {
            method: 'POST',
            body: payload,
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${OPENAI_API_KEY}`,
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

                // Parse OpenAI SSE format: data: {"choices":[{"delta":{"content":"..."}}]}
                let content = chunk;
                try {
                    const parsed = JSON.parse(chunk);
                    content = parsed.choices &&
                        parsed.choices[0] &&
                        parsed.choices[0].delta &&
                        parsed.choices[0].delta.content;

                    if (content === undefined || content === null || content === '') return;
                } catch (_) {
                    // If not JSON, treat the raw chunk as content (some servers send plain text)
                }

                const now = Date.now();

                if (firstChunkTime === null) {
                    firstChunkTime = now;
                    ttft_ms.add(now - startTime);
                    console.log(`[VU ${__VU}] ✓ First chunk received after ${now - startTime}ms: "${content}"`);
                }

                if (lastChunkTime !== null) {
                    chunk_iat_ms.add(now - lastChunkTime);
                }

                lastChunkTime = now;
                lastContent = content;
                chunkCount++;
            }
        }
    );

    const ok = check(res, { 'status 200': (r) => r.status === 200 });

    if (!ok) {
        chat_failed.add(1);
        if (res.status === 401) {
            console.error(`[VU ${__VU}] ✗ 401 Unauthorized — check OPENAI_API_KEY`);
        } else if (res.status === 429) {
            console.warn(`[VU ${__VU}] ✗ 429 Rate Limited — server is throttling`);
        } else if (res.status === 502 || res.status === 503) {
            console.warn(`[VU ${__VU}] ✗ ${res.status} — server overloaded or unavailable`);
        } else if (res.status === 0) {
            console.error(`[VU ${__VU}] ✗ No response after ${Date.now() - startTime}ms`);
        } else {
            console.warn(`[VU ${__VU}] ✗ Failed — status=${res.status}`);
        }
    } else if (chunkCount > 0 && !timedOut) {
        chat_success.add(1);
        tokens_per_request.add(chunkCount);
        total_duration_ms.add(Date.now() - startTime);
        console.log(`[VU ${__VU}] ✓ Stream complete — ${chunkCount} chunks in ${Date.now() - startTime}ms, last chunk: "${lastContent}"`);
    } else {
        chat_failed.add(1);
        if (timedOut) {
            console.error(`[VU ${__VU}] ✗ Failed — first chunk timeout after ${FIRST_CHUNK_TIMEOUT_MS}ms`);
        } else if (res.status === 200 && chunkCount === 0) {
            console.warn(`[VU ${__VU}] ✗ Failed — stream opened successfully but server returned no chunks (empty response)`);
        } else {
            console.warn(`[VU ${__VU}] ✗ Failed — status=${res.status} chunks=${chunkCount}`);
        }
    }

    if (OPENAI_SLEEP_MAX > 0) {
        sleep(Math.random() * (OPENAI_SLEEP_MAX - OPENAI_SLEEP_MIN) + OPENAI_SLEEP_MIN);
    }
}

// =============================================================================
// Summary
// =============================================================================
export function handleSummary(data) {
    const chatTotal = data.metrics.chat_total ? data.metrics.chat_total.values.count : 0;
    const chatSuccess = data.metrics.chat_success ? data.metrics.chat_success.values.count : 0;
    const chatFailed = data.metrics.chat_failed ? data.metrics.chat_failed.values.count : 0;
    const interrupted = chatTotal - chatSuccess - chatFailed;

    const ttft = data.metrics.ttft_ms;
    const iat = data.metrics.chunk_inter_arrival_ms;
    const tpr = data.metrics.tokens_per_request;
    const dur = data.metrics.total_duration_ms;

    const fmt = (metric, key) => {
        try {
            const v = metric && metric.values && metric.values[key];
            return (v !== undefined && v !== null) ? v.toFixed(2) : 'N/A';
        } catch (_) {
            return 'N/A';
        }
    };

    const summary = `
─── OpenAI Benchmark Summary ──────────────────────
  Model:       ${OPENAI_MODEL}
  Server:      ${OPENAI_BASE_URL}
  Stages:      ${JSON.stringify(STAGES)}

  Chat Requests
    Total:       ${chatTotal}
    Success:     ${chatSuccess}
    Failed:      ${chatFailed}
    Interrupted: ${interrupted}

  TTFT (Time to First Token)
    min:         ${fmt(ttft, 'min')}ms
    p(95):       ${fmt(ttft, 'p(95)')}ms
    p(99):       ${fmt(ttft, 'p(99)')}ms
    max:         ${fmt(ttft, 'max')}ms

  Chunk Inter-Arrival
    min:         ${fmt(iat, 'min')}ms
    p(95):       ${fmt(iat, 'p(95)')}ms
    p(99):       ${fmt(iat, 'p(99)')}ms
    max:         ${fmt(iat, 'max')}ms

  Tokens per Request
    min:         ${fmt(tpr, 'min')}
    avg:         ${fmt(tpr, 'avg')}
    max:         ${fmt(tpr, 'max')}

  Total Duration per Request
    min:         ${fmt(dur, 'min')}ms
    avg:         ${fmt(dur, 'avg')}ms
    max:         ${fmt(dur, 'max')}ms
────────────────────────────────────────────────────
`;

    console.log(summary);
    return {};
}

// =============================================================================
// Teardown
// =============================================================================
export function teardown() {
    console.log('─── OpenAI Benchmark complete ───');
    console.log(`Model: ${OPENAI_MODEL}`);
    console.log(`Server: ${OPENAI_BASE_URL}`);
}
