# Load .env first (skip for help and env targets)
ifneq ($(MAKECMDGOALS),env)
ifneq ($(MAKECMDGOALS),help)
ifneq (,$(wildcard .env))
    include .env
    export
else
    $(error No .env file found. Run: make env ENV=<name>  e.g. make env ENV=scraping.example)
endif
endif
endif

# Configuration
PRESET ?= smoke
SCRAPING_URLS_FILE ?=
TIMESTAMP := $(shell date +%Y-%m-%d_%H-%M-%S)
RUN_DIR := results/$(TIMESTAMP)_$(PRESET)
OUT := $(RUN_DIR)/results.json
PLOT := $(RUN_DIR)/scraping_$(PRESET).png
PYTHON := $(if $(wildcard ../venv/bin/python3),../venv/bin/python3,python3)

.PHONY: help all run plot clean list env env-show smoke breaking soak spike stress

# Default target
help:
	@echo "CloudCIX Scraping API Load Testing"
	@echo ""
	@echo "Quick Start:"
	@echo "  1. make env ENV=scraping.example     — Set up environment"
	@echo "  2. make run PRESET=smoke             — Run smoke test"
	@echo "  3. make plot                         — Plot latest results"
	@echo ""
	@echo "Available targets:"
	@echo "  make env ENV=<name>                  — Switch environment (scraping_example)"
	@echo "  make run PRESET=<preset>             — Run test with preset"
	@echo "  make plot [RUN=<dir>]                — Plot results"
	@echo "  make list                            — List all past runs"
	@echo "  make clean                           — Delete all results"
	@echo ""
	@echo "Available presets: smoke, stress, breaking, soak, spike"
	@echo ""
	@echo "Custom options:"
	@echo "  SCRAPING_URLS_FILE=scraping_urls/custom.json — Use custom URLs"
	@echo "  SCRAPING_DOCUMENT_TYPE=pdf_hi_res            — Override document type"


all: run plot

$(RUN_DIR):
	mkdir -p $(RUN_DIR)

run: $(RUN_DIR)
	k6 run \
		--out json=$(OUT) \
		-e SCRAPING_API_URL=$(SCRAPING_API_URL) \
		-e SCRAPING_API_KEY=$(SCRAPING_API_KEY) \
		-e SCRAPING_DOCUMENT_TYPE=$(SCRAPING_DOCUMENT_TYPE) \
		$(if $(SCRAPING_URLS_FILE),-e SCRAPING_URLS_FILE=$(SCRAPING_URLS_FILE),) \
		$(if $(SCRAPING_EXCLUSIONS),-e SCRAPING_EXCLUSIONS=$(SCRAPING_EXCLUSIONS),) \
		$(if $(SCRAPING_SLEEP_MIN),-e SCRAPING_SLEEP_MIN=$(SCRAPING_SLEEP_MIN),) \
		$(if $(SCRAPING_SLEEP_MAX),-e SCRAPING_SLEEP_MAX=$(SCRAPING_SLEEP_MAX),) \
		-e PRESET=$(PRESET) \
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
	$(error ENV is required. Usage: make env ENV=scraping.example)
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
