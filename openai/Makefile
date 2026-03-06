# Load .env first (skip for help and env targets)
ifneq ($(MAKECMDGOALS),env)
ifneq ($(MAKECMDGOALS),help)
ifneq ($(MAKECMDGOALS),generate)
ifneq (,$(wildcard .env))
    include .env
    export
else
    $(error No .env file found. Run: make env ENV=<name>  e.g. make env ENV=openai.example)
endif
endif
endif
endif

# Configuration
PRESET ?= breaking
QUESTIONS_FILE ?=
TIMESTAMP := $(shell date +%Y-%m-%d_%H-%M-%S)
RUN_DIR := results/$(TIMESTAMP)_$(PRESET)
OUT := $(RUN_DIR)/results.json
PLOT := $(RUN_DIR)/ttft_$(PRESET).png
PYTHON := $(if $(wildcard ../venv/bin/python3),../venv/bin/python3,python3)

.PHONY: help all run plot clean list env env-show generate analyze-tokens smoke breaking soak spike stress

# Default target
help:
	@echo "OpenAI-Compatible API Load Testing"
	@echo ""
	@echo "Quick Start:"
	@echo "  1. make env ENV=openai.example       — Set up environment"
	@echo "  2. make run PRESET=smoke             — Run smoke test"
	@echo "  3. make plot                         — Plot latest results"
	@echo ""
	@echo "Available targets:"
	@echo "  make env ENV=<name>                  — Switch environment (openai_example, openai_prod)"
	@echo "  make run PRESET=<preset>             — Run test with preset"
	@echo "  make plot [RUN=<dir>]                — Plot results"
	@echo "  make generate                        — Generate exact-token prompts (HuggingFace tokenizers)"
	@echo "  make analyze-tokens                  — Analyze token distribution"
	@echo "  make list                            — List all past runs"
	@echo "  make clean                           — Delete all results"
	@echo ""
	@echo "Available presets: smoke, stress, breaking, soak, spike"
	@echo ""
	@echo "Custom options:"
	@echo "  QUESTIONS_FILE=questions/custom.json — Use custom questions"
	@echo "  OPENAI_SLEEP_MIN=100                 — Min sleep between requests (ms)"
	@echo "  OPENAI_SLEEP_MAX=1000                — Max sleep between requests (ms)"


all: run plot

$(RUN_DIR):
	mkdir -p $(RUN_DIR)

run: $(RUN_DIR)
	k6 run \
		--out json=$(OUT) \
		-e OPENAI_BASE_URL=$(OPENAI_BASE_URL) \
		-e OPENAI_API_KEY=$(OPENAI_API_KEY) \
		-e OPENAI_MODEL=$(OPENAI_MODEL) \
		-e OPENAI_TEMPERATURE=$(OPENAI_TEMPERATURE) \
		-e OPENAI_TOP_P=$(OPENAI_TOP_P) \
		$(if $(OPENAI_SEED),-e OPENAI_SEED=$(OPENAI_SEED),) \
		$(if $(OPENAI_SLEEP_MIN),-e OPENAI_SLEEP_MIN=$(OPENAI_SLEEP_MIN),) \
		$(if $(OPENAI_SLEEP_MAX),-e OPENAI_SLEEP_MAX=$(OPENAI_SLEEP_MAX),) \
		-e FIRST_CHUNK_TIMEOUT_MS=$(FIRST_CHUNK_TIMEOUT_MS) \
		-e PRESET=$(PRESET) \
		$(if $(QUESTIONS_FILE),-e QUESTIONS_FILE=$(QUESTIONS_FILE),) \
		test.js 2>&1 | tee $(RUN_DIR)/summary.txt

plot:
	@if [ -f "$(OUT)" ]; then \
		$(PYTHON) plot.py "$(OUT)" "$(PRESET)"; \
	else \
		echo "No results found. Run 'make run' first."; \
	fi

clean:
	rm -rf results/

list:
	@ls -1dt results/*/ 2>/dev/null | head -20 || echo "No results yet"

env:
ifndef ENV
	$(error ENV is required. Usage: make env ENV=openai.example)
endif
	ln -sf envs/$(ENV).env .env
	@echo "Switched to $(ENV)"

env-show:
	@echo "Active env: $$(readlink .env 2>/dev/null || echo '.env (not a symlink)')"
	@echo ""
	@cat .env

# Shortcuts
smoke: PRESET=smoke
smoke: run plot

breaking: PRESET=breaking
breaking: run plot

soak: PRESET=soak
soak: run plot

spike: PRESET=spike
spike: run plot

stress: PRESET=stress
stress: run plot
