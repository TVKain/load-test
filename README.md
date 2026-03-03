# CloudCIX Chatbot Load Testing

A k6-based load testing suite for benchmarking the CloudCIX chatbot API. Measures Time to First Chunk (TTFT) and chunk inter-arrival time under various load profiles, with automatic plot generation.

---

## Requirements

- [k6](https://k6.io/docs/getting-started/installation/) with the [xk6-sse](https://github.com/phymbert/xk6-sse) extension
- Python 3 with `pandas` and `matplotlib`

```bash
pip install pandas matplotlib
```

---

## Folder Structure

```
├── load_test.js          # Main k6 test script
├── plot.py               # Generates TTFT plot from results
├── Makefile              # Orchestrates benchmark and plot
├── .env                  # Symlink to active env file (git ignored)
├── .gitignore
├── envs/                 # Environment configurations
│   ├── example.env       # Template — copy this to get started
│   ├── production.env    # Production credentials (git ignored)
│   ├── staging.env       # Staging credentials (git ignored)
│   └── dev.env           # Dev credentials (git ignored)
├── presets/              # Load profile definitions (one file per preset)
│   ├── smoke.json        # 1 VU, sanity check
│   ├── breaking.json     # Ramp up until the server breaks (default)
│   ├── soak.json         # Sustained load to detect degradation over time
│   ├── spike.json        # Sudden burst then back to normal
│   └── stress.json       # Gradual increase beyond expected capacity
├── questions/            # (Optional) Custom question datasets
│   ├── sample.json       # 30 CloudCIX-specific questions (included)
│   ├── cloudcix.json     # Broader CloudCIX question set (see docs below)
│   └── sharegpt.json     # Real-world general questions from ShareGPT (see docs below)
└── results/              # All benchmark results (git ignored, auto-created)
    └── {timestamp}_{preset}/
        ├── results.json       # Raw k6 output
        ├── ttft_{preset}.png  # TTFT plot
        └── summary.txt        # Full terminal output
```

---

## Getting Started

```bash
# 1. Copy the example env and fill in your credentials
cp envs/example.env envs/production.env
vim envs/production.env

# 2. Switch to your environment
make env ENV=production

# 3. Run a smoke test to verify everything works
make smoke

# 4. Run a full breaking point test
make breaking
```

---

## Switching Environments

Each environment has its own file in `envs/`. The active environment is a symlink at `.env`.

```bash
# Switch to staging
make env ENV=staging

# Switch to production
make env ENV=production

# Switch to dev
make env ENV=dev

# See which environment is active
make env-show
```

---

## How to Run

```bash
# Run with the default preset (breaking)
make

# Run a specific preset
make smoke
make breaking
make soak
make spike
make stress

# Override preset without changing .env
make run PRESET=spike

# Run with a custom questions dataset
make run PRESET=soak QUESTIONS_FILE=./questions/cloudcix.json
make run PRESET=soak QUESTIONS_FILE=./questions/sharegpt.json

# List all past runs
make list

# Replot an existing run without re-running the test
python3 plot.py results/2026-03-03_14-22-01_breaking/results.json breaking

# Clean all results
make clean
```

---

## Adding a New Preset

1. Create a new file in the `presets/` folder:

```bash
touch presets/my_preset.json
```

2. Define your stages — each stage has a `duration` and a `target` VU count:

```json
[
    { "duration": "30s", "target": 10 },
    { "duration": "1m",  "target": 50 },
    { "duration": "1m",  "target": 50 },
    { "duration": "30s", "target": 0  }
]
```

3. Run it:

```bash
make run PRESET=my_preset
```

No changes needed to `load_test.js`, `plot.py`, or the `Makefile`.

---

## Adding a New Environment

1. Create a new env file in `envs/`:

```bash
cp envs/example.env envs/my_env.env
vim envs/my_env.env
```

2. Switch to it:

```bash
make env ENV=my_env
```

---

## Custom Question Datasets

By default, the test uses a built-in pool of 40 questions covering general CloudCIX topics. Each VU picks a question at random from the pool on every iteration.

To use your own questions, create a JSON file containing a flat array of strings:

```json
[
    "How does billing work in CloudCIX?",
    "What payment methods are accepted?",
    "How do I view my invoice?",
    "Can I get a refund?"
]
```

Then pass it in at runtime:

```bash
make run PRESET=soak QUESTIONS_FILE=./questions/my_questions.json
```

The file path is relative to the project root. The test will log how many questions were loaded at startup so you can confirm it picked up the right file.

### Included Datasets

#### `questions/cloudcix.json` — CloudCIX Domain Questions

A curated set of questions specifically about CloudCIX — virtual machines, networking, storage, billing, security, and the API. Best used when you want to stress test the chatbot on its intended domain and measure how it handles topic-specific load.

```bash
make run PRESET=soak QUESTIONS_FILE=./questions/cloudcix.json
```

To generate this file, run the included helper script:

```bash
python3 scripts/build_cloudcix_questions.py
```

#### `questions/sharegpt.json` — Real-World General Questions (ShareGPT)

A dataset of real opening questions extracted from the [ShareGPT52K](https://huggingface.co/datasets/RyokoAI/ShareGPT52K) dataset — 52K real human-AI conversations collected from ChatGPT users and released under CC0. Using this dataset simulates realistic, unpredictable day-to-day usage rather than a narrow topic pool, which is ideal for soak and stress testing.


---

## Metrics

| Metric | Description |
|---|---|
| `ttft_ms` | Time from request start to first chunk received (ms) |
| `chunk_inter_arrival_ms` | Time between consecutive chunks (ms) |
| `chat_total` | Total chat requests attempted |
| `chat_success` | Chat requests that completed successfully |
| `chat_failed` | Chat requests that failed (non-200, timeout, or no chunks) |
| `conv_total` | Total conversation creation attempts |
| `conv_success` | Successful conversation creations |
| `conv_failed` | Failed conversation creations |

---

## Understanding the Plot

Each run produces a four-panel plot:

- **Panel 1** — TTFT scatter (raw dots) with cumulative p99 trend line and a final p99 reference line
- **Panel 2** — Cumulative chat requests (total, success, failed) over time
- **Panel 3** — Cumulative conversation requests (total, success, failed) over time
- **Panel 4** — Active VU count over time

Vertical dashed lines mark stage boundaries so you can correlate exactly when TTFT started degrading with the VU count at that moment. The stats box at the bottom shows `min`, `p99`, and `max` TTFT across the full run.

---

## Preset Reference

| Preset | Purpose | When to use |
|---|---|---|
| `smoke` | 1 VU, 30s | Verify the test works before a full run |
| `breaking` | Ramp 10→100 VUs | Find where the server starts failing |
| `soak` | 50 VUs for 8h | Detect memory leaks or gradual degradation |
| `spike` | Burst to 100 VUs | Test recovery from sudden traffic surges |
| `stress` | Gradual ramp to 15 VUs | Understand how performance degrades under load |

---

## Environment Variables

All variables are set via the active `.env` file. Use `make env ENV=<name>` to switch.

| Variable | Default | Description |
|---|---|---|
| `CLOUDCIX_API_BASE` | `api.cloudcix.com` | Base API domain |
| `CLOUDCIX_API_USERNAME` | — | Auth email |
| `CLOUDCIX_API_PASSWORD` | — | Auth password |
| `CLOUDCIX_API_KEY` | — | API key |
| `CHATBOT_NAME` | `Guiden` | Name of the chatbot to test |
| `FIRST_CHUNK_TIMEOUT_MS` | `300000` | Max time to wait for first chunk (ms) |
| `PRESET` | `breaking` | Load profile preset to use |
| `QUESTIONS_FILE` | _(unset)_ | Path to a custom JSON questions dataset |