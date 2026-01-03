SHELL := /bin/bash
PY ?= uv run

# Workflow Manifest (JSON)
MANIFEST ?= configs/manifest.json
PROFILE ?= production

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
	$(if $(CLUSTER_CAP),TV_CLUSTER_CAP=$(CLUSTER_CAP))
ENV_VARS := $(shell TV_MANIFEST_PATH=$(MANIFEST) TV_PROFILE=$(PROFILE) $(ENV_OVERRIDES) $(PY) -m tradingview_scraper.settings --export-env | sed 's/export //')
$(foreach var,$(ENV_VARS),$(eval $(var)))
$(foreach var,$(ENV_VARS),$(eval export $(shell echo "$(var)" | cut -d= -f1)))
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

.PHONY: help
help: ## Display this help screen
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
	uv sync

env-check: ## Validate manifest and configuration integrity
	$(PY) scripts/validate_manifest.py

# --- SCAN Namespace ---
scan-run: ## Execute composable discovery scanners
	@echo ">>> STAGE: DISCOVERY (Composable Pipelines)"
	TV_EXPORT_RUN_ID=$(RUN_ID) $(PY) scripts/compose_pipeline.py --profile $(PROFILE)

scan-audit: ## Lint scanner configurations
	$(PY) scripts/lint_universe_configs.py

# --- DATA Namespace ---
data-prep-raw: ## Aggregate scans and initialize raw pool
	$(PY) scripts/select_top_universe.py --mode raw
	-$(PY) scripts/validate_portfolio_artifacts.py --mode raw --only-health

data-fetch: ## Ingest historical market data
	$(PY) scripts/prepare_portfolio_data.py
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
	$(PY) scripts/enrich_candidates_metadata.py
	$(PY) scripts/natural_selection.py

port-optimize: ## Strategic asset allocation (Convex)
	$(PY) scripts/optimize_clustered_v2.py

port-test: ## Execute 3D benchmarking tournament
	@echo ">>> Running Multi-Engine Tournament Mode..."
	$(PY) scripts/backtest_engine.py --tournament


port-analyze: ## Factor, correlation, and regime analysis
	$(PY) scripts/correlation_report.py --hrp --min-col-frac 0.2
	$(PY) scripts/audit_antifragility.py
	$(PY) scripts/analyze_clusters.py
	$(PY) scripts/visualize_factor_map.py
	$(PY) scripts/research_regime_v2.py
	$(PY) scripts/detect_hedge_anchors.py
	$(PY) scripts/monitor_cluster_drift.py

# --- REPORT Namespace ---
port-report: ## Generate unified quant reports and tear-sheets
	$(PY) scripts/generate_reports.py
	$(PY) scripts/generate_portfolio_report.py
	$(PY) scripts/generate_audit_summary.py

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
	$(PY) python -m scripts.run_production_pipeline --profile $(PROFILE) --manifest $(MANIFEST)

flow-dev: ## Rapid iteration development execution
	$(MAKE) flow-production PROFILE=development

# --- CLEAN Namespace ---
clean-run: ## Wipe current run artifacts
	rm -f summaries
	rm -f data/lakehouse/portfolio_candidates*.json data/lakehouse/portfolio_returns.pkl data/lakehouse/portfolio_meta.json
	rm -f data/lakehouse/portfolio_clusters*.json data/lakehouse/portfolio_optimized_v2.json
	rm -f data/lakehouse/antifragility_stats.json data/lakehouse/selection_audit.json data/lakehouse/cluster_drift.json data/lakehouse/tmp_bt_*

clean-all: clean-run ## Deep wipe including exports and all summaries
	rm -rf export/*.csv export/*.json export/*/*.csv export/*/*.json
	rm -rf $(SUMMARIES_ROOT)

# --- META Namespace ---
meta-refresh: ## Rebuild symbol metadata for current candidates
	$(PY) scripts/build_metadata_catalog.py --candidates-file data/lakehouse/portfolio_candidates.json

meta-refresh-all: ## Rebuild entire symbol metadata catalog (Maintenance)
	$(PY) scripts/build_metadata_catalog.py --from-catalog --catalog-path $(META_CATALOG_PATH)

meta-audit: ## Verify metadata integrity and timezones
	$(PY) scripts/audit_metadata_pit.py
	$(PY) scripts/audit_metadata_timezones.py
	$(PY) scripts/audit_metadata_catalog.py
