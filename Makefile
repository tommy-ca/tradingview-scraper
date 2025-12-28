SHELL := /bin/bash
PY ?= uv run
BATCH ?= 5
LOOKBACK ?= 200
BACKFILL ?= 1
GAPFILL ?= 1
SUMMARY_DIR ?= summaries
GIST_ID ?= e888e1eab0b86447c90c26e92ec4dc36

# Selection & Risk Parameters
TOP_N ?= 3
THRESHOLD ?= 0.4
CLUSTER_CAP ?= 0.25

.PHONY: sync sync-dev test lint format typecheck clean-all clean-exports clean-daily clean-run daily-run accept-state scans-local scans-crypto scans-bonds scans-forex-mtf scans prep-raw prune select prep align recover analyze corr-report factor-map regime-check hedge-anchors drift-check optimize-v2 backtest backtest-all backtest-report validate audit-health audit-logic audit-data audit report drift-monitor display gist heatmap finalize health-report

# --- Discovery (Scanners) ---

scans-local:
	bash scripts/run_local_scans.sh

scans-crypto:
	bash scripts/run_crypto_scans.sh

scans-bonds:
	$(PY) -m tradingview_scraper.bond_universe_selector --config configs/bond_etf_trend_momentum.yaml --export json

scans-forex-mtf:
	$(PY) -m tradingview_scraper.cfd_universe_selector --config configs/forex_mtf_monthly_weekly_daily.yaml --export json

scans: scans-local scans-crypto scans-bonds scans-forex-mtf

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
	$(MAKE) clean-daily
	$(MAKE) scans
	$(MAKE) prep-raw
	$(MAKE) prune TOP_N=$(TOP_N) THRESHOLD=$(THRESHOLD)
	$(MAKE) align LOOKBACK=$(LOOKBACK)
	$(MAKE) analyze
	$(MAKE) finalize

# After reviewing and implementing, snapshot current optimized as "actual" state.
accept-state:
	$(PY) scripts/track_portfolio_state.py --accept

clean-run: clean-all
	$(MAKE) scans
	$(MAKE) prep-raw
	$(MAKE) prune
	$(MAKE) align
	$(MAKE) analyze
	$(MAKE) finalize
