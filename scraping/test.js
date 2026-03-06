import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Trend } from 'k6/metrics';

// =============================================================================
// Configuration
// =============================================================================
const SCRAPING_API_URL = __ENV.SCRAPING_API_URL || 'https://ml.cloudcix.com/scraping/';
const SCRAPING_API_KEY = __ENV.SCRAPING_API_KEY;
const SCRAPING_DOCUMENT_TYPE = __ENV.SCRAPING_DOCUMENT_TYPE || 'html';
const SCRAPING_URLS_FILE = __ENV.SCRAPING_URLS_FILE;
const SCRAPING_SLEEP_MIN = parseFloat(__ENV.SCRAPING_SLEEP_MIN || '0.5');
const SCRAPING_SLEEP_MAX = parseFloat(__ENV.SCRAPING_SLEEP_MAX || '2.5');

// Optional: HTML exclusions (JSON string)
const SCRAPING_EXCLUSIONS_RAW = __ENV.SCRAPING_EXCLUSIONS;
let SCRAPING_EXCLUSIONS = null;
if (SCRAPING_EXCLUSIONS_RAW) {
    try {
        SCRAPING_EXCLUSIONS = JSON.parse(SCRAPING_EXCLUSIONS_RAW);
    } catch (e) {
        console.error(`Failed to parse SCRAPING_EXCLUSIONS: ${e.message}`);
    }
}

if (!SCRAPING_API_KEY) throw new Error('SCRAPING_API_KEY is required');
if (!SCRAPING_URLS_FILE) throw new Error('SCRAPING_URLS_FILE is required (e.g. html, pdf, pdf_hi_res)');

const PRESET = __ENV.PRESET || 'smoke';
let STAGES;

try {
    STAGES = JSON.parse(open(`../shared/presets/${PRESET}.json`));
} catch (e) {
    throw new Error(`Unknown preset "${PRESET}" — make sure shared/presets/${PRESET}.json exists`);
}

// =============================================================================
// URLs — loaded from scraping_urls/<SCRAPING_URLS_FILE>.json
// =============================================================================
const URLS_PATH = `scraping_urls/${SCRAPING_URLS_FILE}.json`;
let URLS;
try {
    URLS = JSON.parse(open(URLS_PATH));
    if (!Array.isArray(URLS) || URLS.length === 0) {
        throw new Error('URLs file must be a non-empty JSON array');
    }
} catch (e) {
    throw new Error(`Failed to load URLs file "${URLS_PATH}": ${e.message}`);
}

// =============================================================================
// Metrics
// =============================================================================
const scraping_total = new Counter('scraping_total');
const scraping_success = new Counter('scraping_success');
const scraping_failed = new Counter('scraping_failed');
const scraping_latency_ms = new Trend('scraping_latency_ms', true);
const response_size_bytes = new Trend('response_size_bytes', true);

// =============================================================================
// Load Profile
// =============================================================================
export const options = {
    scenarios: {
        [PRESET]: {
            executor: 'ramping-vus',
            stages: STAGES,
            gracefulStop: '60s',
            gracefulRampDown: '30s',
        },
    },
    thresholds: {
        'scraping_latency_ms': ['p(95)<30000'],
        'scraping_failed': ['count<100'],
    },
};

// =============================================================================
// Setup
// =============================================================================
export function setup() {
    console.log(`Scraping API URL: ${SCRAPING_API_URL}`);
    console.log(`Document type: ${SCRAPING_DOCUMENT_TYPE}`);
    console.log(`Exclusions: ${SCRAPING_EXCLUSIONS ? JSON.stringify(SCRAPING_EXCLUSIONS) : 'none'}`);
    console.log(`Sleep between iterations: ${SCRAPING_SLEEP_MIN}–${SCRAPING_SLEEP_MAX}s`);
    console.log(`Stages: ${JSON.stringify(STAGES)}`);
    console.log(`URLs pool: ${URLS.length} URLs from ${URLS_PATH}`);
    return {};
}

// =============================================================================
// Default VU
// =============================================================================
export default function () {
    const url = URLS[Math.floor(Math.random() * URLS.length)];
    
    scraping_total.add(1);

    const urlPreview = url.length > 80 ? `${url.slice(0, 80)}...` : url;
    console.log(`[VU ${__VU}] ⏳ Scraping: ${urlPreview}`);

    const requestBody = {
        list: [url],
        document_type: SCRAPING_DOCUMENT_TYPE,
        api_key: SCRAPING_API_KEY,
    };

    if (SCRAPING_EXCLUSIONS) {
        requestBody.exclusions = SCRAPING_EXCLUSIONS;
    }

    const startTime = Date.now();
    
    const res = http.post(
        SCRAPING_API_URL,
        JSON.stringify(requestBody),
        {
            headers: {
                'Content-Type': 'application/json',
            },
            timeout: '300s',
        }
    );

    const latency = Date.now() - startTime;
    scraping_latency_ms.add(latency);

    const ok = check(res, {
        'status 200': (r) => r.status === 200,
        'has response body': (r) => r.body && r.body.length > 0,
    });

    if (ok) {
        scraping_success.add(1);
        response_size_bytes.add(res.body.length);
        console.log(`[VU ${__VU}] ✓ Success — ${latency}ms, ${(res.body.length / 1024).toFixed(2)} KB`);
    } else {
        scraping_failed.add(1);
        if (res.status === 401 || res.status === 403) {
            console.error(`[VU ${__VU}] ✗ ${res.status} Unauthorized — check SCRAPING_API_KEY`);
        } else if (res.status === 429) {
            console.warn(`[VU ${__VU}] ✗ 429 Rate Limited`);
        } else if (res.status === 500 || res.status === 502 || res.status === 503) {
            console.warn(`[VU ${__VU}] ✗ ${res.status} Server Error`);
        } else if (res.status === 0) {
            console.error(`[VU ${__VU}] ✗ Timeout after ${latency}ms`);
        } else {
            console.warn(`[VU ${__VU}] ✗ Failed — status=${res.status}, latency=${latency}ms`);
        }
    }

    if (SCRAPING_SLEEP_MAX > 0) {
        sleep(Math.random() * (SCRAPING_SLEEP_MAX - SCRAPING_SLEEP_MIN) + SCRAPING_SLEEP_MIN);
    }
}

// =============================================================================
// Summary
// =============================================================================
export function handleSummary(data) {
    const scrapingTotal = data.metrics.scraping_total ? data.metrics.scraping_total.values.count : 0;
    const scrapingSuccess = data.metrics.scraping_success ? data.metrics.scraping_success.values.count : 0;
    const scrapingFailed = data.metrics.scraping_failed ? data.metrics.scraping_failed.values.count : 0;
    const interrupted = scrapingTotal - scrapingSuccess - scrapingFailed;

    const latency = data.metrics.scraping_latency_ms ? data.metrics.scraping_latency_ms.values : null;
    const responseSize = data.metrics.response_size_bytes ? data.metrics.response_size_bytes.values : null;

    let summary = '\n';
    summary += '='.repeat(80) + '\n';
    summary += 'SCRAPING API BENCHMARK SUMMARY\n';
    summary += '='.repeat(80) + '\n\n';

    summary += `Document Type: ${SCRAPING_DOCUMENT_TYPE}\n`;
    summary += `Total Requests: ${scrapingTotal}\n`;
    summary += `  ✓ Successful: ${scrapingSuccess}\n`;
    summary += `  ✗ Failed: ${scrapingFailed}\n`;
    if (interrupted > 0) {
        summary += `  ⚠ Interrupted: ${interrupted}\n`;
    }
    summary += '\n';

    if (latency) {
        summary += 'Latency (ms):\n';
        summary += `  min: ${latency.min.toFixed(0)}\n`;
        summary += `  p50: ${latency.med.toFixed(0)}\n`;
        summary += `  p95: ${latency['p(95)'].toFixed(0)}\n`;
        summary += `  p99: ${latency['p(99)'].toFixed(0)}\n`;
        summary += `  max: ${latency.max.toFixed(0)}\n`;
        summary += `  avg: ${latency.avg.toFixed(0)}\n`;
        summary += '\n';
    }

    if (responseSize) {
        summary += 'Response Size (KB):\n';
        summary += `  min: ${(responseSize.min / 1024).toFixed(2)}\n`;
        summary += `  p50: ${(responseSize.med / 1024).toFixed(2)}\n`;
        summary += `  p95: ${(responseSize['p(95)'] / 1024).toFixed(2)}\n`;
        summary += `  max: ${(responseSize.max / 1024).toFixed(2)}\n`;
        summary += `  avg: ${(responseSize.avg / 1024).toFixed(2)}\n`;
        summary += '\n';
    }

    summary += '='.repeat(80) + '\n';

    return {
        'stdout': summary,
    };
}
