SHELL := /bin/bash
PY ?= uv run
BATCH ?= 5
LOOKBACK ?= 200
BACKFILL ?= 1
GAPFILL ?= 1
SUMMARY_DIR ?= summaries
META_CATALOG_PATH ?= data/lakehouse/symbols.parquet
META_REFRESH ?= 0
META_AUDIT ?= 0
GIST_ID ?= e888e1eab0b86447c90c26e92ec4dc36

# Selection & Risk Parameters
TOP_N ?= 3
THRESHOLD ?= 0.4
CLUSTER_CAP ?= 0.25

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
.PHONY: scan-local scan-crypto scan-bonds scan-forex-mtf scan-all scan
.PHONY: scans-local scans-crypto scans-bonds scans-forex-mtf scans

# Portfolio pipeline aliases
.PHONY: portfolio-prep-raw portfolio-prune portfolio-align portfolio-analyze portfolio-finalize portfolio-accept-state portfolio-validate portfolio-audit

# Portfolio pipeline
.PHONY: prep-raw prune select prep align recover analyze corr-report factor-map regime-check hedge-anchors drift-check optimize-v2 backtest backtest-all backtest-report validate audit-health audit-logic audit-data audit report drift-monitor display gist heatmap finalize health-report

help:
	@echo "Entry points:"
	@echo "  run-daily        Daily incremental portfolio run"
	@echo "  clean-run        Full reset run (blank slate)"
	@echo "  scan-all         Run all scanners"
	@echo "  meta-validate    Refresh + offline metadata audits"
	@echo "  meta-audit       Offline + online metadata parity sample"
	@echo "  daily-run META_REFRESH=1 META_AUDIT=1  Offline metadata gates"
	@echo "  daily-run META_REFRESH=1 META_AUDIT=2  Include online parity audit"

# --- Discovery (Scanners) ---

scan-local:
	bash scripts/run_local_scans.sh

scan-crypto:
	bash scripts/run_crypto_scans.sh

scan-bonds:
	$(PY) -m tradingview_scraper.bond_universe_selector --config configs/bond_etf_trend_momentum.yaml --export json

scan-forex-mtf:
	$(PY) -m tradingview_scraper.cfd_universe_selector --config configs/forex_mtf_monthly_weekly_daily.yaml --export json

scan-all: scan-local scan-crypto scan-bonds scan-forex-mtf
scan: scan-all

# Legacy aliases (kept for compatibility)
scans-local: scan-local
scans-crypto: scan-crypto
scans-bonds: scan-bonds
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
	$(PY) scripts/backtest_engine.py --profile min_variance --train 120 --test 20 --step 20 || $(PY) scripts/backtest_engine.py --profile min_variance --train 40 --test 10 --step 10
	$(PY) scripts/backtest_engine.py --profile risk_parity --train 120 --test 20 --step 20 || $(PY) scripts/backtest_engine.py --profile risk_parity --train 40 --test 10 --step 10
	$(PY) scripts/backtest_engine.py --profile max_sharpe --train 120 --test 20 --step 20 || $(PY) scripts/backtest_engine.py --profile max_sharpe --train 40 --test 10 --step 10
	$(PY) scripts/backtest_engine.py --profile barbell --train 120 --test 20 --step 20 || $(PY) scripts/backtest_engine.py --profile barbell --train 40 --test 10 --step 10

backtest-report:
	$(PY) scripts/generate_backtest_report.py

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
	mkdir -p $(SUMMARY_DIR)
	$(PY) scripts/correlation_report.py --hrp --out-dir $(SUMMARY_DIR) --min-col-frac 0.2
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

finalize: optimize-v2 backtest audit report drift-monitor gist

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
	bash scripts/push_summaries_to_gist.sh

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
	rm -rf export/*.csv export/*.json

clean-all: clean-exports
	rm -rf $(SUMMARY_DIR)/*.txt $(SUMMARY_DIR)/*.md $(SUMMARY_DIR)/*.png
	rm -f data/lakehouse/portfolio_*

# Daily incremental cleanup: keeps lakehouse candle cache and last implemented state.
clean-daily: clean-exports
	rm -rf $(SUMMARY_DIR)/*.txt $(SUMMARY_DIR)/*.md $(SUMMARY_DIR)/*.png
	rm -f data/lakehouse/portfolio_candidates*.json data/lakehouse/portfolio_returns.pkl data/lakehouse/portfolio_meta.json
	rm -f data/lakehouse/portfolio_clusters*.json data/lakehouse/portfolio_optimized_v2.json
	rm -f data/lakehouse/antifragility_stats.json data/lakehouse/selection_audit.json data/lakehouse/cluster_drift.json data/lakehouse/tmp_bt_*

# Daily institutional run (incremental, all markets).
# Pushes summaries to gist before and after the run (for safety and early auth validation).
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
