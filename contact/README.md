# Contact API Load Test

Benchmarks the CloudCIX Contact API (conversation creation + SSE answer streaming).

## Quick Start

```bash
# 1. Configure your environment
cp envs/contact.example.env envs/mytest.env
vim envs/mytest.env  # Add your credentials

# 2. Activate environment
make env ENV=mytest

# 3. Run a smoke test
make smoke

# 4. Run other presets
make stress
make breaking
make run PRESET=soak QUESTIONS_FILE=cloudcix
```

## Configuration

Edit your `.env` file (created via `make env ENV=<name>`):

| Variable | Required | Description |
|---|---|---|
| `CLOUDCIX_API_BASE` | Yes | API domain (e.g., `api.cloudcix.com`) |
| `CLOUDCIX_API_USERNAME` | Yes | Auth email |
| `CLOUDCIX_API_PASSWORD` | Yes | Auth password |
| `CLOUDCIX_API_KEY` | Yes | API key |
| `CHATBOT_NAME` | No | Chatbot name (default: `Guiden`) |
| `QUESTIONS_FILE` | No | Questions dataset (e.g., `cloudcix`, `sharegpt`) |
| `PRESET` | No | Load profile (default: `breaking`) |

## Metrics

- `ttft_ms` — Time to first token
- `chunk_inter_arrival_ms` — Time between chunks
- `chat_total/success/failed` — Request counters
- `conv_total/success/failed` — Conversation creation counters

## Results

Results are saved to `results/{timestamp}_{preset}/`:
- `results.json` — Raw k6 metrics
- `ttft_{preset}.png` — 4-panel visualization
- `summary.txt` — Terminal output

## Questions

Question datasets are in `questions/`:
- `cloudcix.json` — CloudCIX-specific questions
- `sharegpt.json` — Real-world questions from ShareGPT

Add your own by creating a JSON array of strings in `questions/`.
