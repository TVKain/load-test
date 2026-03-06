# =============================================================================
# k6-cloudcix-chatbot — Root Makefile (Convenience Wrapper)
# =============================================================================
# This Makefile provides shortcuts to run individual test modules.
# Each test module (contact/, openai/, scraping/) has its own Makefile.
#
# Quick Start:
#   make contact-run PRESET=smoke ENV=contact.example
#   make openai-run PRESET=stress ENV=openai.example
#   make scraping-run PRESET=smoke ENV=scraping.example
#
# Or navigate to each directory:
#   cd contact && make help
# =============================================================================

.PHONY: help venv clean

# Default target
help:
	@echo "k6 CloudCIX Load Testing — Root Makefile"
	@echo ""
	@echo "Available test modules:"
	@echo "  contact/   — Contact API (formerly chatbot)"
	@echo "  openai/    — OpenAI-compatible API"
	@echo "  scraping/  — CloudCIX Scraping API"
	@echo ""
	@echo "Convenience targets:"
	@echo "  make contact-run PRESET=<preset> ENV=<env>    — Run contact test"
	@echo "  make openai-run PRESET=<preset> ENV=<env>     — Run OpenAI test"
	@echo "  make scraping-run PRESET=<preset> ENV=<env>   — Run scraping test"
	@echo ""
	@echo "  make contact-plot RUN=<run_dir>               — Plot contact results"
	@echo "  make openai-plot RUN=<run_dir>                — Plot OpenAI results"
	@echo "  make scraping-plot RUN=<run_dir>              — Plot scraping results"
	@echo ""
	@echo "For detailed usage, navigate to each directory:"
	@echo "  cd contact && make help"
	@echo "  cd openai && make help"
	@echo "  cd scraping && make help"

# =============================================================================
# Python Virtual Environment
# =============================================================================
.PHONY: all run plot clean list env env-show smoke breaking soak spike stress

all: run plot

$(RUN_DIR):
	mkdir -p $(RUN_DIR)

venv:
	python3 -m venv venv
	./venv/bin/pip install --upgrade pip
	./venv/bin/pip install pandas matplotlib
	@echo "✓ Virtual environment created in ./venv/"
	@echo "  Shared by all test modules"

clean:
	@echo "Cleaning all results..."
	rm -rf contact/results/* openai/results/* scraping/results/*
	@echo "✓ All test results cleaned"

# =============================================================================
# Contact Test Shortcuts
# =============================================================================
contact-run:
ifndef PRESET
	$(error PRESET is required. Usage: make contact-run PRESET=smoke ENV=contact.example)
endif
ifndef ENV
	$(error ENV is required. Usage: make contact-run PRESET=smoke ENV=contact.example)
endif
	cd contact && $(MAKE) env ENV=$(ENV) && $(MAKE) run PRESET=$(PRESET)

contact-plot:
ifdef RUN
	cd contact && $(MAKE) plot RUN=$(RUN)
else
	cd contact && $(MAKE) plot
endif

# =============================================================================
# OpenAI Test Shortcuts
# =============================================================================
openai-run:
ifndef PRESET
	$(error PRESET is required. Usage: make openai-run PRESET=smoke ENV=openai.example)
endif
ifndef ENV
	$(error ENV is required. Usage: make openai-run PRESET=smoke ENV=openai.example)
endif
	cd openai && $(MAKE) env ENV=$(ENV) && $(MAKE) run PRESET=$(PRESET)

openai-plot:
ifdef RUN
	cd openai && $(MAKE) plot RUN=$(RUN)
else
	cd openai && $(MAKE) plot
endif

openai-generate:
	cd openai && $(MAKE) generate

# =============================================================================
# Scraping Test Shortcuts
# =============================================================================
scraping-run:
ifndef PRESET
	$(error PRESET is required. Usage: make scraping-run PRESET=smoke ENV=scraping.example)
endif
ifndef ENV
	$(error ENV is required. Usage: make scraping-run PRESET=smoke ENV=scraping.example)
endif
	cd scraping && $(MAKE) env ENV=$(ENV) && $(MAKE) run PRESET=$(PRESET)

scraping-plot:
ifdef RUN
	cd scraping && $(MAKE) plot RUN=$(RUN)
else
	cd scraping && $(MAKE) plot
endif

.DEFAULT_GOAL := help
