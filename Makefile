# =============================================================================
# Configuration
# =============================================================================
PRESET         ?= breaking
QUESTIONS_FILE ?=   # filename only, e.g. sample or sharegpt (no path, no .json)
TIMESTAMP      := $(shell date +%Y-%m-%d_%H-%M-%S)
RUN_DIR        := results/$(TIMESTAMP)_$(PRESET)
OUT            := $(RUN_DIR)/results.json
PLOT           := $(RUN_DIR)/ttft_$(PRESET).png

# Load .env and export all variables
ifneq (,$(wildcard .env))
    include .env
    export
else
    $(error No .env file found. Run: make env ENV=<name>  e.g. make env ENV=production)
endif

# =============================================================================
# Targets
# =============================================================================
.PHONY: all run plot clean list env env-show smoke breaking soak spike stress

all: run plot

$(RUN_DIR):
	mkdir -p $(RUN_DIR)

run: $(RUN_DIR)
	k6 run \
		--out json=$(OUT) \
		-e CLOUDCIX_API_BASE=$(CLOUDCIX_API_BASE) \
		-e CLOUDCIX_API_USERNAME=$(CLOUDCIX_API_USERNAME) \
		-e CLOUDCIX_API_PASSWORD=$(CLOUDCIX_API_PASSWORD) \
		-e CLOUDCIX_API_KEY=$(CLOUDCIX_API_KEY) \
		-e CHATBOT_NAME=$(CHATBOT_NAME) \
		-e FIRST_CHUNK_TIMEOUT_MS=$(FIRST_CHUNK_TIMEOUT_MS) \
		-e PRESET=$(PRESET) \
		$(if $(QUESTIONS_FILE),-e QUESTIONS_FILE=$(QUESTIONS_FILE),) \
		load_test.js 2>&1 | tee $(RUN_DIR)/summary.txt

plot:
	python3 plot.py $(OUT) $(PRESET) $(PLOT)

# List all past runs
list:
	@echo "Past runs:"
	@ls -1 results/ 2>/dev/null || echo "No runs yet"

# Switch environment — usage: make env ENV=staging
env:
ifndef ENV
	$(error ENV is required. Usage: make env ENV=staging)
endif
	ln -sf envs/$(ENV).env .env
	@echo "Switched to $(ENV)"

# Show active environment
env-show:
	@echo "Active env: $$(readlink .env 2>/dev/null || echo '.env (not a symlink)')"
	@echo ""
	@cat .env

clean:
	rm -rf results/

# Preset shortcuts
smoke:
	$(MAKE) all PRESET=smoke
breaking:
	$(MAKE) all PRESET=breaking
soak:
	$(MAKE) all PRESET=soak
spike:
	$(MAKE) all PRESET=spike
stress:
	$(MAKE) all PRESET=stress