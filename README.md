# CloudCIX Benchmarks

A collection of k6-based load testing suites for benchmarking CloudCIX APIs. Each test is self-contained with its own configuration, data, and results.

## Test Suites

- **[contact/](contact/)** — CloudCIX Contact API (conversation + SSE streaming)
- **[openai/](openai/)** — OpenAI-compatible `/chat/completions` endpoints (vLLM, llama.cpp, Ollama, etc.)
- **[scraping/](scraping/)** — CloudCIX Scraping API (HTML/PDF document extraction)

## Quick Start

Each test is independent. Navigate to the test directory and follow its README:

```bash
# Test the Contact API
cd contact/
make env ENV=contact.example
make smoke

# Test an OpenAI-compatible endpoint
cd openai/
make env ENV=openai.example
make run PRESET=smoke QUESTIONS_FILE=cloudcix

# Test the Scraping API
cd scraping/
make env ENV=scraping.example
make run PRESET=smoke SCRAPING_URLS_FILE=html
```

## Requirements

- [k6](https://k6.io/docs/getting-started/installation/) (with [xk6-sse](https://github.com/phymbert/xk6-sse) extension for streaming tests)
- Python 3 with pandas and matplotlib (for plotting)

```bash
# Create virtual environment (run from root)
python3 -m venv venv
venv/bin/pip install pandas matplotlib
```

## Structure

```
k6-cloudcix-benchmarks/
├── shared/
│   └── presets/              # Load profiles (smoke, stress, breaking, etc.)
│       ├── smoke.json
│       ├── stress.json
│       └── ...
├── contact/                  # Self-contained Contact API test
│   ├── README.md
│   ├── Makefile
│   ├── test.js
│   ├── plot.py
│   ├── questions/
│   ├── envs/
│   └── results/
├── openai/                   # Self-contained OpenAI test
│   ├── README.md
│   ├── Makefile
│   ├── test.js
│   ├── plot.py
│   ├── generate_questions_hf.py
│   ├── token_lengths.py
│   ├── requirements.txt
│   ├── questions/
│   ├── envs/
│   └── results/
└── scraping/                 # Self-contained Scraping test
    ├── README.md
    ├── Makefile
    ├── test.js
    ├── plot.py
    ├── scraping_urls/
    ├── envs/
    └── results/
```

## Shared Presets

All tests use the same load profiles located in `shared/presets/`:

| Preset | Purpose | Profile |
|---|---|---|
| `smoke` | Sanity check | 1 VU for 30s |
| `breaking` | Find breaking point | Ramp 10→100 VUs |
| `stress` | Gradual degradation | Slow ramp to 100 VUs |
| `soak` | Memory leaks | 50 VUs for 8 hours |
| `spike` | Burst recovery | Sudden jump to 100 VUs |

## Adding a New Test

1. Create a new directory with the test name
2. Add `test.js`, `plot.py`, and `Makefile`
3. Create `envs/`, `results/`, and any data directories
4. Reference presets via `../shared/presets/${PRESET}.json`
5. Document usage in a local README.md

Each test is completely independent - no changes to other tests or root files required.

## Root Convenience Commands

You can optionally run tests from the root directory:

```bash
# From root directory
cd contact && make smoke
cd openai && make run PRESET=stress QUESTIONS_FILE=sharegpt
cd scraping && make run PRESET=smoke SCRAPING_URLS_FILE=pdf
```

## Documentation

See each test's README for detailed usage, metrics, and configuration:
- [contact/README.md](contact/README.md)
- [openai/README.md](openai/README.md)
- [scraping/README.md](scraping/README.md)
