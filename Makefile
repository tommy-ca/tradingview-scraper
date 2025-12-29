SHELL := /bin/bash
PY ?= uv run

# Workflow Manifest (JSON)
MANIFEST ?= configs/manifest.json
PROFILE ?= production

# Bridge JSON Manifest to Shell Environment
# This allows us to use manifest settings in Makefile logic and sub-processes.
ifneq ($(wildcard $(MANIFEST)),)
    # Extract variables from the selected profile using settings.py CLI
    # We strip 'export ' to get 'KEY=VALUE' which $(eval) can consume.
    ENV_VARS := $(shell TV_MANIFEST_PATH=$(MANIFEST) TV_PROFILE=$(PROFILE) $(PY) -m tradingview_scraper.settings --export-env | sed 's/export //')
    $(foreach var,$(ENV_VARS),$(eval $(var)))
    # Export these variables to all sub-processes
    $(foreach var,$(ENV_VARS),$(eval export $(shell echo "$(var)" | cut -d= -f1)))
endif

# Defaults (if not set in manifest or environment)
BATCH ?= 5
LOOKBACK ?= 200
BACKFILL ?= 1
GAPFILL ?= 1
TOP_N ?= 3
THRESHOLD ?= 0.4
CLUSTER_CAP ?= 0.25
META_REFRESH ?= 0
META_AUDIT ?= 0
GIST_ID ?= e888e1eab0b86447c90c26e92ec4dc36

# Backtest Defaults
BACKTEST_TRAIN ?= 120
BACKTEST_TEST ?= 20
BACKTEST_STEP ?= 20

# Tournament Defaults
TOURNAMENT_ENGINES ?= custom,skfolio,riskfolio,pyportfolioopt,cvxportfolio
TOURNAMENT_PROFILES ?= min_variance,hrp,max_sharpe,barbell

# Generated artifacts live under artifacts/ (ignored by git)
ARTIFACTS_DIR ?= artifacts
SUMMARIES_ROOT ?= $(ARTIFACTS_DIR)/summaries
# `latest` points to the last successful finalized run under $(SUMMARIES_ROOT)/runs/<RUN_ID>
SUMMARY_DIR ?= $(SUMMARIES_ROOT)/latest
# The current run's artifacts land here (run-scoped).
SUMMARY_RUN_DIR ?= $(SUMMARIES_ROOT)/runs/$(TV_RUN_ID)

META_CATALOG_PATH ?= data/lakehouse/symbols.parquet

# Scan run scoping (export/<run_id>/...)
# Priority: explicit TV_EXPORT_RUN_ID > explicit RUN_ID > generated timestamp
ifneq ($(origin TV_EXPORT_RUN_ID), undefined)
RUN_ID := $(TV_EXPORT_RUN_ID)
else
ifeq ($(origin RUN_ID), undefined)
RUN_ID := $(shell date +%Y%m%d-%H%M%S)
endif
endif

export RUN_ID
ifeq ($(origin TV_EXPORT_RUN_ID), undefined)
TV_EXPORT_RUN_ID := $(RUN_ID)
endif
export TV_EXPORT_RUN_ID

# Use a single shared run id for all artifacts in a workflow.
ifeq ($(origin TV_RUN_ID), undefined)
TV_RUN_ID := $(RUN_ID)
endif
export TV_RUN_ID

.PHONY: help

# Environment / tooling
.PHONY: sync sync-dev test lint format typecheck

# Cleanup
.PHONY: clean-exports clean-all clean-daily clean-run

# High-level entry points
.PHONY: run-daily run-clean run-scan daily-run clean-run accept-state

# Metadata catalogs
.PHONY: meta-refresh meta-stats meta-audit-offline meta-audit meta-explore meta-validate

# Scanners
.PHONY: scan-local scan-crypto scan-bonds scan-forex-base scan-forex-mtf scan-all scan scan-lint
.PHONY: scans-local scans-crypto scans-bonds scans-forex-base scans-forex-mtf scans

# Forex analysis
.PHONY: forex-analyze forex-analyze-fast

# Portfolio pipeline aliases
.PHONY: portfolio-prep-raw portfolio-prune portfolio-align portfolio-analyze portfolio-finalize portfolio-accept-state portfolio-validate portfolio-audit

# Portfolio pipeline
.PHONY: prep-raw prune select prep align recover analyze corr-report factor-map regime-check hedge-anchors drift-check optimize-v2 backtest backtest-all backtest-report backtest-tournament tournament tournament-report validate audit-health audit-logic audit-data audit report drift-monitor display gist gist-run promote-latest heatmap finalize health-report

help:
	@echo "Entry points:"
	@echo "  run-daily        Daily incremental portfolio run"
	@echo "  clean-run        Full reset run (blank slate)"
	@echo "  scan-all         Run all scanners"
	@echo "  scan-forex-base  Run forex base universe scan"
	@echo "  forex-analyze    Analyze forex base universe"
	@echo "  scan-lint        Lint all scan configs"
	@echo "  meta-validate    Refresh + offline metadata audits"
	@echo "  meta-audit       Offline + online metadata parity sample"
	@echo "  daily-run META_REFRESH=1 META_AUDIT=1  Offline metadata gates"
	@echo "  daily-run META_REFRESH=1 META_AUDIT=2  Include online parity audit"

# --- Discovery (Scanners) ---

scan-local:
	TV_EXPORT_RUN_ID=$(RUN_ID) bash scripts/run_local_scans.sh

scan-crypto:
	TV_EXPORT_RUN_ID=$(RUN_ID) bash scripts/run_crypto_scans.sh

scan-bonds:
	TV_EXPORT_RUN_ID=$(RUN_ID) $(PY) -m tradingview_scraper.bond_universe_selector --config configs/bond_etf_trend_momentum.yaml --export json

scan-forex-base:
	TV_EXPORT_RUN_ID=$(RUN_ID) $(PY) -m tradingview_scraper.cfd_universe_selector --config configs/forex_base_universe.yaml --export json --print-format table

scan-forex-mtf:
	TV_EXPORT_RUN_ID=$(RUN_ID) $(PY) -m tradingview_scraper.cfd_universe_selector --config configs/forex_mtf_monthly_weekly_daily.yaml --export json

scan-all: scan-local scan-crypto scan-bonds scan-forex-mtf
scan: scan-all

scan-lint:
	$(PY) scripts/lint_universe_configs.py

# --- Forex Base Universe Analysis ---

forex-analyze: scan-forex-base
	FOREX_BACKFILL=$(BACKFILL) FOREX_GAPFILL=$(GAPFILL) $(PY) scripts/analyze_forex_universe.py --export-symbol forex_base_universe

forex-analyze-fast: scan-forex-base
	$(PY) scripts/analyze_forex_universe.py --export-symbol forex_base_universe --skip-history

# Legacy aliases (kept for compatibility)
scans-local: scan-local
scans-crypto: scan-crypto
scans-bonds: scan-bonds
scans-forex-base: scan-forex-base
scans-forex-mtf: scan-forex-mtf
scans: scan-all

# --- Metadata Catalog (Symbols + Exchanges) ---

meta-refresh:
	$(PY) scripts/build_metadata_catalog.py --from-catalog --catalog-path $(META_CATALOG_PATH)

meta-stats:
	$(PY) scripts/check_catalog_stats.py

meta-audit-offline:
	$(PY) scripts/audit_metadata_pit.py
	$(PY) scripts/audit_metadata_timezones.py

meta-audit: meta-audit-offline
	$(PY) scripts/audit_metadata_catalog.py

meta-explore:
	$(PY) scripts/explore_metadata_catalogs.py

# Refresh + audit (offline) in one command.
meta-validate: meta-refresh meta-audit-offline

# --- Entry Points (Convenience Aliases) ---

run-daily: daily-run
run-clean: clean-run
run-scan: scan-all

portfolio-prep-raw: prep-raw
portfolio-prune: prune
portfolio-align: align
portfolio-analyze: analyze
portfolio-finalize: finalize
portfolio-accept-state: accept-state
portfolio-validate: validate
portfolio-audit: audit

# --- Validation & Auditing ---

backtest: backtest-all backtest-report

backtest-all:
	@echo ">>> Running Walk-Forward Validation for all profiles..."
	$(PY) scripts/backtest_engine.py --profile min_variance --train $(BACKTEST_TRAIN) --test $(BACKTEST_TEST) --step $(BACKTEST_STEP)
	$(PY) scripts/backtest_engine.py --profile risk_parity --train $(BACKTEST_TRAIN) --test $(BACKTEST_TEST) --step $(BACKTEST_STEP)
	$(PY) scripts/backtest_engine.py --profile max_sharpe --train $(BACKTEST_TRAIN) --test $(BACKTEST_TEST) --step $(BACKTEST_STEP)
	$(PY) scripts/backtest_engine.py --profile barbell --train $(BACKTEST_TRAIN) --test $(BACKTEST_TEST) --step $(BACKTEST_STEP)

backtest-report:
	$(PY) scripts/generate_backtest_report.py

backtest-tournament:
	@echo ">>> Running Multi-Engine Tournament Mode..."
	CLUSTER_CAP=$(CLUSTER_CAP) $(PY) scripts/backtest_engine.py --tournament --engines $(TOURNAMENT_ENGINES) --profiles $(TOURNAMENT_PROFILES) --train $(BACKTEST_TRAIN) --test $(BACKTEST_TEST) --step $(BACKTEST_STEP)

tournament-report: backtest-report

tournament: backtest-tournament tournament-report

validate: audit-data backtest

audit-health:
	@echo ">>> Auditing Data Health & Integrity"
	$(PY) scripts/validate_portfolio_artifacts.py --mode selected --only-health

audit-logic:
	@echo ">>> Auditing Portfolio Quantitative Logic"
	$(PY) scripts/validate_portfolio_artifacts.py --mode selected --only-logic

audit-data: audit-health audit-logic

audit: audit-logic

health-report:
	$(PY) scripts/validate_portfolio_artifacts.py --mode selected --only-health
	$(PY) scripts/validate_portfolio_artifacts.py --mode raw --only-health

# --- Tiered Selection Logic ---


# Raw health check here is informational; hard gate occurs after backfill in `prune`.
prep-raw:
	$(PY) scripts/select_top_universe.py --mode raw
	-$(PY) scripts/validate_portfolio_artifacts.py --mode raw --only-health

prune:
	@echo ">>> Phase 1: Lightweight Backfill (60d) for statistical pruning"
	CANDIDATES_FILE=data/lakehouse/portfolio_candidates_raw.json $(MAKE) prep BACKFILL=1 GAPFILL=1 LOOKBACK=60 BATCH=5
	$(PY) scripts/validate_portfolio_artifacts.py --mode raw --only-health
	$(PY) scripts/audit_antifragility.py
	$(MAKE) select TOP_N=$(TOP_N) THRESHOLD=$(THRESHOLD)
	$(PY) scripts/enrich_candidates_metadata.py

select:
	$(PY) scripts/natural_selection.py --top-n $(TOP_N) --threshold $(THRESHOLD)

# --- Data Preparation (Self-Healing) ---

prep:
	PORTFOLIO_MAX_SYMBOLS=200 PORTFOLIO_BATCH_SIZE=$(BATCH) PORTFOLIO_LOOKBACK_DAYS=$(LOOKBACK) PORTFOLIO_BACKFILL=$(BACKFILL) PORTFOLIO_GAPFILL=$(GAPFILL) $(PY) scripts/prepare_portfolio_data.py
	@if [ "$(GAPFILL)" = "1" ]; then \
		echo "Running final repair pass..."; \
		$(PY) scripts/repair_portfolio_gaps.py --type all; \
	fi

align:
	@echo ">>> Phase 2: High Integrity Backfill (200d) for final winners"
	$(MAKE) prep BACKFILL=1 GAPFILL=1 LOOKBACK=$(LOOKBACK) BATCH=2
	$(MAKE) audit-health


recover:
	$(PY) scripts/recover_universe.py

# --- Analysis (Risk & Regime) ---

analyze: corr-report factor-map regime-check hedge-anchors drift-check

corr-report:
	$(PY) scripts/correlation_report.py --hrp --min-col-frac 0.2
	$(PY) scripts/analyze_clusters.py

factor-map:
	$(PY) scripts/visualize_factor_map.py

regime-check:
	$(PY) scripts/research_regime_v2.py

hedge-anchors:
	$(PY) scripts/detect_hedge_anchors.py

drift-check:
	$(PY) scripts/monitor_cluster_drift.py

# --- Implementation (Optimization & Dashboard) ---

finalize:
	$(MAKE) optimize-v2
	$(MAKE) backtest
	$(MAKE) audit
	$(MAKE) report
	$(MAKE) drift-monitor
	$(MAKE) gist-run
	$(MAKE) promote-latest

optimize-v2:
	CLUSTER_CAP=$(CLUSTER_CAP) $(PY) scripts/optimize_clustered_v2.py

report:
	$(PY) scripts/generate_portfolio_report.py
	$(PY) scripts/generate_audit_summary.py

drift-monitor:
	$(PY) scripts/track_portfolio_state.py

display:
	$(PY) scripts/display_portfolio_dashboard.py

gist:
	SUMMARY_DIR=$(SUMMARY_DIR) GIST_ID=$(GIST_ID) bash scripts/push_summaries_to_gist.sh

gist-run:
	SUMMARY_DIR=$(SUMMARY_RUN_DIR) GIST_ID=$(GIST_ID) bash scripts/push_summaries_to_gist.sh

promote-latest:
	$(PY) python -c "from tradingview_scraper.settings import get_settings; get_settings().promote_summaries_latest()"

heatmap:
	$(PY) scripts/visualize_matrix_cli.py

# --- Utility & Lifecycle ---

sync:
	uv sync

sync-dev:
	uv sync --extra dev

test:
	$(PY) pytest

lint:
	uvx ruff check .

format:
	uvx ruff format .

typecheck:
	uvx ty check

clean-exports:
	rm -rf export/*.csv export/*.json export/*/*.csv export/*/*.json

clean-all: clean-exports
	# Legacy + new artifact outputs
	rm -rf summaries
	rm -rf $(SUMMARIES_ROOT)
	rm -f data/lakehouse/portfolio_*

# Daily incremental cleanup: keeps lakehouse candle cache and last implemented state.
clean-daily: clean-exports
	# Keep run history in $(SUMMARIES_ROOT)/runs and preserve `latest` (last successful run).
	rm -rf summaries
	rm -f data/lakehouse/portfolio_candidates*.json data/lakehouse/portfolio_returns.pkl data/lakehouse/portfolio_meta.json
	rm -f data/lakehouse/portfolio_clusters*.json data/lakehouse/portfolio_optimized_v2.json
	rm -f data/lakehouse/antifragility_stats.json data/lakehouse/selection_audit.json data/lakehouse/cluster_drift.json data/lakehouse/tmp_bt_*

# Daily institutional run (incremental, all markets).
# Pushes summary artifacts to gist before and after the run (for safety and early auth validation).
daily-run:
	$(MAKE) gist
	@if [ "$(META_REFRESH)" = "1" ]; then echo ">>> Refreshing metadata catalogs"; $(MAKE) meta-refresh; fi
	@if [ "$(META_AUDIT)" = "1" ]; then echo ">>> Auditing metadata catalogs (offline)"; $(MAKE) meta-audit-offline; fi
	@if [ "$(META_AUDIT)" = "2" ]; then echo ">>> Auditing metadata catalogs (online)"; $(MAKE) meta-audit; fi
	$(MAKE) clean-daily
	$(MAKE) scan-all
	$(MAKE) portfolio-prep-raw
	$(MAKE) portfolio-prune TOP_N=$(TOP_N) THRESHOLD=$(THRESHOLD)
	$(MAKE) portfolio-align LOOKBACK=$(LOOKBACK)
	$(MAKE) portfolio-analyze
	$(MAKE) portfolio-finalize

# After reviewing and implementing, snapshot current optimized as "actual" state.
accept-state:
	$(PY) scripts/track_portfolio_state.py --accept

clean-run: clean-all
	$(MAKE) scan-all
	$(MAKE) portfolio-prep-raw
	$(MAKE) portfolio-prune
	$(MAKE) portfolio-align
	$(MAKE) portfolio-analyze
	$(MAKE) portfolio-finalize
