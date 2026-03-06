# OpenAI API Load Test

Benchmarks OpenAI-compatible `/chat/completions` endpoints (vLLM, llama.cpp, Ollama, etc.).

## Quick Start

```bash
# 1. Configure your environment
cp envs/openai.example.env envs/myserver.env
vim envs/myserver.env  # Add your server details

# 2. Activate environment
make env ENV=myserver

# 3. Run a smoke test
make run PRESET=smoke QUESTIONS_FILE=cloudcix

# 4. Run stress test
make stress QUESTIONS_FILE=sharegpt
```

## Configuration

Edit your `.env` file:

| Variable | Required | Description |
|---|---|---|
| `OPENAI_BASE_URL` | Yes | Server URL (e.g., `http://localhost:8000/v1`) |
| `OPENAI_API_KEY` | Yes | API key / Bearer token |
| `OPENAI_MODEL` | Yes | Model name |
| `OPENAI_TEMPERATURE` | No | Sampling temperature (default: `0`) |
| `OPENAI_TOP_P` | No | Nucleus sampling (default: `1`) |
| `OPENAI_SEED` | No | Fixed seed for reproducibility |
| `OPENAI_SLEEP_MIN/MAX` | No | Sleep between iterations (default: `0.5–2.5s`) |
| `QUESTIONS_FILE` | Yes | Questions dataset name |

## Tokenizer Tools

Generate exact-token prompts using HuggingFace tokenizers:

```bash
# Install dependencies
pip install -r requirements.txt

# Generate dataset
python3 generate_questions_hf.py \
    --model-id mistralai/Mistral-Large-3-675B-Instruct-2512 \
    --output-file questions/mistral_256t.json \
    --dataset-size 200 \
    --tokens-per-prompt 256 \
    --seed 1337

# Inspect token counts
python3 token_lengths.py \
    --questions-file questions/mistral_256t.json \
    --tokenizer hf \
    --model-id mistralai/Mistral-Large-3-675B-Instruct-2512
```

## Metrics

- `ttft_ms` — Time to first content token
- `chunk_inter_arrival_ms` — Time between chunks
- `tokens_per_request` — Number of content chunks
- `total_duration_ms` — Full request duration
- `chat_total/success/failed` — Request counters

## Results

Results in `results/{timestamp}_{preset}/`:
- `results.json` — Raw k6 metrics
- `ttft_{preset}.png` — 2-panel plot
- `summary.txt` — Terminal output
