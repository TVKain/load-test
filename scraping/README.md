# Scraping API Load Test

Benchmarks the CloudCIX Scraping API for HTML/PDF document extraction.

## Quick Start

```bash
# 1. Configure your environment
cp envs/scraping.example.env envs/mytest.env
vim envs/mytest.env  # Add your API key

# 2. Activate environment
make env ENV=mytest

# 3. Run tests
make run PRESET=smoke SCRAPING_URLS_FILE=html
make run PRESET=stress SCRAPING_URLS_FILE=pdf SCRAPING_DOCUMENT_TYPE=pdf
```

## Configuration

Edit your `.env` file:

| Variable | Required | Description |
|---|---|---|
| `SCRAPING_API_URL` | No | API endpoint (default: `https://ml.cloudcix.com/scraping/`) |
| `SCRAPING_API_KEY` | Yes | API key for authentication |
| `SCRAPING_DOCUMENT_TYPE` | No | Type: `html`, `pdf`, or `pdf_hi_res` (default: `html`) |
| `SCRAPING_URLS_FILE` | Yes | URL dataset name (e.g., `html`, `pdf`, `pdf_hi_res`) |
| `SCRAPING_EXCLUSIONS` | No | JSON string for HTML exclusions |
| `SCRAPING_SLEEP_MIN/MAX` | No | Sleep between iterations (default: `0.5–2.5s`) |

### HTML Exclusions Example

```bash
SCRAPING_EXCLUSIONS='{"exclusion_tags":["script","style"],"exclusion_classes":["footer","header"]}'
```

## URL Datasets

Located in `scraping_urls/`:
- `html.json` — HTML pages (CloudCIX docs, Wikipedia, etc.)
- `pdf.json` — PDF documents (arXiv papers)
- `pdf_hi_res.json` — PDFs for high-resolution extraction

Add your own by creating a JSON array of URLs.

## Metrics

- `scraping_latency_ms` — Total request latency
- `response_size_bytes` — Response size
- `scraping_total/success/failed` — Request counters

## Results

Results in `results/{timestamp}_{preset}/`:
- `results.json` — Raw k6 metrics
- `scraping_{preset}.png` — 2-panel plot (latency distribution + results)
- `summary.txt` — Terminal output
