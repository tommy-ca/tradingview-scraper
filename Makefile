SHELL := /bin/bash
PY ?= uv run

# Workflow Manifest (JSON)
MANIFEST ?= configs/manifest.json
PROFILE ?= $(or $(TV_PROFILE),production)
export PROFILE
export TV_PROFILE := $(PROFILE)

# Bridge JSON Manifest to Shell Environment

ifneq ($(wildcard $(MANIFEST)),)
ENV_OVERRIDES := \
	$(if $(LOOKBACK),TV_LOOKBACK_DAYS=$(LOOKBACK)) \
	$(if $(PORTFOLIO_LOOKBACK_DAYS),TV_PORTFOLIO_LOOKBACK_DAYS=$(PORTFOLIO_LOOKBACK_DAYS)) \
	$(if $(BACKTEST_TRAIN),TV_TRAIN_WINDOW=$(BACKTEST_TRAIN)) \
	$(if $(BACKTEST_TEST),TV_TEST_WINDOW=$(BACKTEST_TEST)) \
	$(if $(BACKTEST_STEP),TV_STEP_SIZE=$(BACKTEST_STEP)) \
	$(if $(BACKTEST_SIMULATOR),TV_BACKTEST_SIMULATOR=$(BACKTEST_SIMULATOR)) \
	$(if $(BACKTEST_SIMULATORS),TV_BACKTEST_SIMULATORS=$(BACKTEST_SIMULATORS)) \
	$(if $(CLUSTER_CAP),TV_CLUSTER_CAP=$(CLUSTER_CAP)) \
	$(if $(SELECTION_MODE),TV_FEATURES__SELECTION_MODE=$(SELECTION_MODE)) \
	$(if $(MIN_DAYS_FLOOR),TV_MIN_DAYS_FLOOR=$(MIN_DAYS_FLOOR))
ENV_VARS = $(shell TV_MANIFEST_PATH=$(MANIFEST) TV_PROFILE=$(PROFILE) $(ENV_OVERRIDES) $(PY) -m tradingview_scraper.settings --export-env | sed 's/export //')
$(foreach var,$(ENV_VARS),$(eval $(var)))
$(foreach var,$(ENV_VARS),$(eval export $(shell echo "$(var)" | cut -d= -f1)))

# Promote institutional (non-TV_) env var names to TV_-prefixed equivalents so
# `get_settings()` consumers see Make/manifest overrides.
#
# - The settings model uses `env_prefix="TV_"`.
# - `--export-env` intentionally prints human-friendly/institutional var names.
# - Without this promotion, `make ... BACKTEST_TRAIN=...` updates the exported
#   `BACKTEST_*` vars but not `TV_*`, so window overrides won't take effect.
ifeq ($(origin TV_LOOKBACK_DAYS), undefined)
export TV_LOOKBACK_DAYS := $(LOOKBACK)
endif
ifeq ($(origin TV_PORTFOLIO_LOOKBACK_DAYS), undefined)
export TV_PORTFOLIO_LOOKBACK_DAYS := $(PORTFOLIO_LOOKBACK_DAYS)
endif
ifeq ($(origin TV_TRAIN_WINDOW), undefined)
export TV_TRAIN_WINDOW := $(BACKTEST_TRAIN)
endif
ifeq ($(origin TV_TEST_WINDOW), undefined)
export TV_TEST_WINDOW := $(BACKTEST_TEST)
endif
ifeq ($(origin TV_STEP_SIZE), undefined)
export TV_STEP_SIZE := $(BACKTEST_STEP)
endif
ifeq ($(origin TV_BACKTEST_SIMULATOR), undefined)
export TV_BACKTEST_SIMULATOR := $(BACKTEST_SIMULATOR)
endif
ifeq ($(origin TV_BACKTEST_SIMULATORS), undefined)
export TV_BACKTEST_SIMULATORS := $(BACKTEST_SIMULATORS)
endif
ifeq ($(origin TV_CLUSTER_CAP), undefined)
export TV_CLUSTER_CAP := $(CLUSTER_CAP)
endif
ifeq ($(origin TV_RAW_POOL_UNIVERSE), undefined)
export TV_RAW_POOL_UNIVERSE := $(RAW_POOL_UNIVERSE)
endif
ifeq ($(origin TV_FEATURES__SELECTION_MODE), undefined)
export TV_FEATURES__SELECTION_MODE := $(SELECTION_MODE)
endif
ifeq ($(origin TV_THRESHOLD), undefined)
export TV_THRESHOLD := $(THRESHOLD)
endif
ifeq ($(origin TV_TOP_N), undefined)
export TV_TOP_N := $(TOP_N)
endif
ifeq ($(origin TV_MIN_MOMENTUM_SCORE), undefined)
export TV_MIN_MOMENTUM_SCORE := $(MIN_MOMENTUM_SCORE)
endif
ifeq ($(origin TV_MIN_DAYS_FLOOR), undefined)
ifneq ($(PORTFOLIO_MIN_DAYS_FLOOR),)
export TV_MIN_DAYS_FLOOR := $(PORTFOLIO_MIN_DAYS_FLOOR)
else
export TV_MIN_DAYS_FLOOR := $(MIN_DAYS_FLOOR)
endif
endif
endif

# Paths
ARTIFACTS_DIR ?= artifacts
SUMMARIES_ROOT ?= $(ARTIFACTS_DIR)/summaries
SUMMARY_DIR ?= $(SUMMARIES_ROOT)/latest
SUMMARY_RUN_DIR ?= $(SUMMARIES_ROOT)/runs/$(TV_RUN_ID)
META_CATALOG_PATH ?= data/lakehouse/symbols.parquet
TARGETED_CANDIDATES ?= data/lakehouse/portfolio_candidates_targeted.json
TARGETED_LOOKBACK ?= 200
TARGETED_BATCH ?= 2

# Run ID Logic
ifneq ($(origin TV_RUN_ID), undefined)
RUN_ID := $(TV_RUN_ID)
else ifneq ($(origin TV_EXPORT_RUN_ID), undefined)
RUN_ID := $(TV_EXPORT_RUN_ID)
else ifeq ($(origin RUN_ID), undefined)
RUN_ID := $(shell date +%Y%m%d-%H%M%S)
endif

export RUN_ID
export TV_RUN_ID := $(RUN_ID)
export TV_EXPORT_RUN_ID := $(RUN_ID)

debug-env: ## Print resolved environment variables
	@echo "PROFILE: $(PROFILE)"
	@echo "TV_DATA__MIN_DAYS_FLOOR: $$TV_DATA__MIN_DAYS_FLOOR"
	@echo "TV_MIN_DAYS_FLOOR: $$TV_MIN_DAYS_FLOOR"
	@$(PY) -m tradingview_scraper.settings --export-env | grep MIN_DAYS_FLOOR
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

# Feature Shortcuts
VETOES ?= 0
ifeq ($(VETOES), 1)
    export TV_FEATURES__FEAT_PREDICTABILITY_VETOES=1
endif

# Logic Shortcuts
STRICT ?= $(STRICT_HEALTH)
ifeq ($(STRICT), 1)
    export TV_STRICT_HEALTH=1
endif

# --- ENV Namespace ---
env-sync: ## Synchronize dependencies using uv
	uv sync --all-extras

env-check: ## Validate manifest and configuration integrity
	$(PY) scripts/validate_manifest.py

# --- TEST Namespace ---
test-parity: ## Run Nautilus parity validation gate
	$(PY) scripts/validate_parity.py

grand-tournament: ## Run multi-dimensional Grand Tournament (Production Mode)
	$(PY) scripts/grand_tournament.py --profile $(PROFILE) --selection-modes "v3.2,v2.1" --mode production

grand-4d: ## Run deep research sweep (Research Mode)
	$(PY) scripts/grand_tournament.py --profile $(PROFILE) --selection-modes "v3.2,v2.1" --rebalance-modes "window,daily" --mode research

live-shadow: ## Run Nautilus in SHADOW mode (Read-only real-time)
	$(PY) scripts/live/run_nautilus_shadow.py --profile $(PROFILE)

smoke-test-nautilus: ## End-to-End Nautilus Parity Smoke Test
	@echo ">>> STAGE: NAUTILUS SMOKE TEST"
	$(MAKE) clean-run
	$(MAKE) flow-production PROFILE=nautilus_parity
	$(MAKE) test-parity

# --- SCAN Namespace ---
scan-run: ## Execute composable discovery scanners
	@echo ">>> STAGE: DISCOVERY (Composable Pipelines)"
	TV_EXPORT_RUN_ID=$(RUN_ID) $(PY) scripts/compose_pipeline.py --profile $(PROFILE)

scan-audit: ## Lint scanner configurations
	$(PY) scripts/lint_universe_configs.py

crypto-scan-audit: ## Validate crypto scanner configurations
	$(PY) scripts/lint_universe_configs.py --path configs/scanners/crypto/
	$(PY) scripts/lint_universe_configs.py --path configs/base/universes/binance*.yaml
	$(PY) scripts/lint_universe_configs.py --path configs/base/templates/crypto*.yaml

# --- DATA Namespace ---
data-prep-raw: ## Aggregate scans and initialize raw pool
	$(PY) scripts/select_top_universe.py --mode raw
	CANDIDATES_FILE=data/lakehouse/portfolio_candidates_raw.json PORTFOLIO_RETURNS_PATH=data/lakehouse/portfolio_returns.pkl PORTFOLIO_META_PATH=data/lakehouse/portfolio_meta.json $(PY) scripts/prepare_portfolio_data.py
	$(PY) scripts/enrich_candidates_metadata.py --candidates data/lakehouse/portfolio_meta.json --returns data/lakehouse/portfolio_returns.pkl
	-$(PY) scripts/validate_portfolio_artifacts.py --mode raw --only-health
	$(PY) scripts/metadata_coverage_guardrail.py --target canonical:data/lakehouse/portfolio_candidates_raw.json:data/lakehouse/portfolio_returns.pkl


data-fetch: ## Ingest historical market data
	$(PY) scripts/prepare_portfolio_data.py
	$(PY) scripts/enrich_candidates_metadata.py --candidates data/lakehouse/portfolio_meta.json
	@if [ "$(GAPFILL)" = "1" ] || [ "$(TV_GAPFILL)" = "1" ]; then \
		echo "Running final aggressive repair pass..."; \
		$(PY) scripts/repair_portfolio_gaps.py --type all --max-fills 15; \
	fi

data-refresh-targeted: ## Force refresh for stale symbols listed in TARGETED_CANDIDATES
	@echo ">>> Targeted refresh using $(TARGETED_CANDIDATES)"
	CANDIDATES_FILE=$(TARGETED_CANDIDATES) PORTFOLIO_BACKFILL=1 PORTFOLIO_GAPFILL=1 PORTFOLIO_FORCE_SYNC=1 PORTFOLIO_LOOKBACK_DAYS=$(TARGETED_LOOKBACK) PORTFOLIO_BATCH_SIZE=$(TARGETED_BATCH) $(PY) scripts/prepare_portfolio_data.py
	$(PY) scripts/repair_portfolio_gaps.py --type all --max-fills 15

data-repair: ## High-intensity gap repair for degraded assets
	$(PY) scripts/recover_universe.py

data-audit: ## Session-Aware health audit (use STRICT_HEALTH=1)
	@STRICT_ARG=""; if [ "$(STRICT_HEALTH)" = "1" ] || [ "$(TV_STRICT_HEALTH)" = "1" ]; then STRICT_ARG="--strict"; fi; \
	$(PY) scripts/validate_portfolio_artifacts.py --mode raw --only-health $$STRICT_ARG
	$(PY) scripts/validate_portfolio_artifacts.py --mode selected --only-health $$STRICT_ARG

# --- PORT Namespace ---
port-select: ## Natural selection and pruning
	$(PY) scripts/enrich_candidates_metadata.py --candidates data/lakehouse/portfolio_meta.json
	$(PY) scripts/natural_selection.py
	$(PY) scripts/metadata_coverage_guardrail.py --target selected:data/lakehouse/portfolio_candidates.json:data/lakehouse/portfolio_returns.pkl

port-optimize: ## Strategic asset allocation (Convex)
	$(PY) scripts/optimize_clustered_v2.py

port-test: ## Execute 3D benchmarking tournament
	@echo ">>> Running Multi-Engine Tournament Mode..."
	$(PY) scripts/backtest_engine.py --mode research

port-drift: ## Monitor portfolio drift vs last implemented state
	$(PY) scripts/maintenance/track_portfolio_state.py

port-shadow-fill: ## Simulate paper execution (Shadow Loop) to reconcile drift
	$(PY) scripts/maintenance/shadow_loop_sim.py

port-analyze: ## Factor, correlation, and regime analysis
	$(PY) scripts/correlation_report.py --hrp
	$(PY) scripts/audit_antifragility.py
	$(PY) scripts/analyze_clusters.py
	$(PY) scripts/visualize_factor_map.py
	$(PY) scripts/research_regime_v2.py
	$(PY) scripts/detect_hedge_anchors.py
	$(PY) scripts/monitor_cluster_drift.py

research-persistence: ## Analyze trend/MR persistence (Requires LOOKBACK=500)
	$(PY) scripts/research/analyze_persistence.py

# --- REPORT Namespace ---
port-report: ## Generate unified quant reports and tear-sheets
	$(PY) scripts/generate_reports.py
	$(PY) scripts/generate_portfolio_report.py
	$(PY) scripts/generate_audit_summary.py

port-deep-audit: ## Generate deep forensic report (Run ID required)
	$(PY) scripts/production/generate_deep_report.py $(RUN_ID)

tournament-scoreboard: ## Generate tournament scoreboard (latest run)
	$(PY) scripts/research/tournament_scoreboard.py --run-id latest

tournament-scoreboard-run: ## Generate tournament scoreboard for RUN_ID
	$(PY) scripts/research/tournament_scoreboard.py --run-id $(RUN_ID)

baseline-audit: ## Validate baseline availability (market/benchmark/raw_pool_ew)
	@STRICT_ARG=""; if [ "$(STRICT_BASELINE)" = "1" ] || [ "$(TV_STRICT_BASELINE)" = "1" ]; then STRICT_ARG="--strict"; fi; \
	RAW_ARG=""; if [ "$(REQUIRE_RAW_POOL)" = "1" ] || [ "$(TV_REQUIRE_RAW_POOL)" = "1" ]; then RAW_ARG="--require-raw-pool"; fi; \
	$(PY) scripts/baseline_audit.py --run-id $(RUN_ID) $$STRICT_ARG $$RAW_ARG

baseline-guardrail: ## Compare raw_pool_ew invariance across two runs (RUN_A, RUN_B)
	@if [ -z "$(RUN_A)" ] || [ -z "$(RUN_B)" ]; then \
		echo "Set RUN_A and RUN_B to run IDs for invariance check."; \
		exit 1; \
	fi
	$(PY) scripts/raw_pool_invariance_guardrail.py --run-a $(RUN_A) --run-b $(RUN_B)

report-sync: ## Synchronize artifacts to private Gist
	@echo ">>> Preparing Gist Payload..."
	@rm -rf artifacts/gist_payload && mkdir -p artifacts/gist_payload
	@cp $(MANIFEST) artifacts/gist_payload/run_manifest.json 2>/dev/null || true
	@find -L artifacts/summaries/latest -maxdepth 1 -name "*.md" -exec cp {} artifacts/gist_payload/ \;
	@find -L artifacts/summaries/latest -maxdepth 1 -name "*.png" -exec cp {} artifacts/gist_payload/ \;
	@find -L artifacts/summaries/latest -maxdepth 1 -name "*.json" -exec cp {} artifacts/gist_payload/ \;
	@SUMMARY_DIR=artifacts/gist_payload GIST_ID=$(GIST_ID) bash scripts/push_summaries_to_gist.sh

# --- FLOW Namespace ---
flow-production: ## Full institutional production lifecycle
	$(PY) python -m scripts.run_production_pipeline --profile $(PROFILE) --manifest $(MANIFEST) --run-id $(TV_RUN_ID)

flow-crypto: ## Full crypto-only production run (BINANCE-only)
	$(MAKE) flow-production PROFILE=crypto_production

flow-prelive: ## Production pre-live workflow (including slow Nautilus simulator)
	$(MAKE) flow-production BACKTEST_SIMULATORS=custom,cvxportfolio,vectorbt,nautilus

flow-dev: ## Rapid iteration development execution
	$(MAKE) flow-production PROFILE=development

flow-meta-production: ## Run multi-sleeve meta-portfolio flow (Fractal Matrix)
	@echo ">>> STAGE: META-PORTFOLIO (Fractal Matrix)"
	$(PY) scripts/build_meta_returns.py --profile meta_production
	$(PY) scripts/optimize_meta_portfolio.py
	@for prof in barbell hrp min_variance equal_weight; do \
		$(PY) scripts/flatten_meta_weights.py --profile $$prof; \
	done
	$(PY) scripts/generate_meta_report.py

# --- CLEAN Namespace ---
clean-run: ## Wipe current run artifacts
	rm -f summaries
	rm -f data/lakehouse/portfolio_candidates*.json data/lakehouse/portfolio_returns.pkl data/lakehouse/portfolio_meta.json
	rm -f data/lakehouse/portfolio_clusters*.json data/lakehouse/portfolio_optimized_v2.json
	rm -f data/lakehouse/antifragility_stats.json data/lakehouse/selection_audit.json data/lakehouse/cluster_drift.json data/lakehouse/tmp_bt_*

clean-archive: ## Archive old run artifacts (Keep 10 latest)
	$(PY) scripts/maintenance/archive_runs.py --keep 10

check-archive: ## Dry run archive to see what would be deleted
	$(PY) scripts/maintenance/archive_runs.py --keep 10 --dry-run

clean-all: clean-run ## Deep wipe including exports and all summaries
	rm -rf export/*.csv export/*.json export/*/*.csv export/*/*.json
	rm -rf $(SUMMARIES_ROOT)

# --- META Namespace ---
meta-refresh: ## Rebuild symbol metadata for current candidates
	$(PY) scripts/build_metadata_catalog.py --candidates-file data/lakehouse/portfolio_candidates.json

meta-refresh-all: ## Rebuild entire symbol metadata catalog (Maintenance)
	$(PY) scripts/build_metadata_catalog.py --from-catalog --catalog-path $(META_CATALOG_PATH)

meta-fetch: ## Fetch execution metadata (lot sizes, min notionals) from exchanges via CCXT
	$(PY) scripts/fetch_execution_metadata.py

meta-audit: ## Verify metadata integrity and timezones
	$(PY) scripts/audit_metadata_pit.py
	$(PY) scripts/audit_metadata_timezones.py
	$(PY) scripts/audit_metadata_catalog.py
