SHELL := /bin/bash
PY ?= uv run
BATCH ?= 5
LOOKBACK ?= 100
BACKFILL ?= 1
GAPFILL ?= 1
SUMMARY_DIR ?= summaries
GIST_ID ?= e888e1eab0b86447c90c26e92ec4dc36

# Selection parameters
TOP_N ?= 3
THRESHOLD ?= 0.4

.PHONY: help update-indexes clean-all clean-exports scans-local scans-crypto scans-bonds scans-forex-mtf scans summaries reports validate prep optimize barbell corr-report pipeline pipeline-quick audit report clean-run hedge-anchors drift-check gist select recover heatmap display regime-check drift-monitor

drift-monitor:
	$(PY) scripts/track_portfolio_state.py

scans-local:
	bash scripts/run_local_scans.sh

scans-crypto:
	bash scripts/run_crypto_scans.sh

scans-bonds:
	$(PY) -m tradingview_scraper.bond_universe_selector --config configs/bond_etf_trend_momentum.yaml --export json

scans-forex-mtf:
	$(PY) -m tradingview_scraper.cfd_universe_selector --config configs/forex_mtf_monthly_weekly_daily.yaml --export json

scans: scans-local scans-crypto scans-bonds scans-forex-mtf

summaries:
	mkdir -p $(SUMMARY_DIR)
	$(PY) scripts/summarize_results.py | tee $(SUMMARY_DIR)/summary_results.txt
	$(PY) scripts/summarize_crypto_results.py | tee $(SUMMARY_DIR)/summary_crypto.txt

prep:
	PORTFOLIO_MAX_SYMBOLS=200 PORTFOLIO_BATCH_SIZE=$(BATCH) PORTFOLIO_LOOKBACK_DAYS=$(LOOKBACK) PORTFOLIO_BACKFILL=$(BACKFILL) PORTFOLIO_GAPFILL=$(GAPFILL) $(PY) scripts/prepare_portfolio_data.py
	@if [ "$(GAPFILL)" = "1" ]; then \
		echo "Running final repair pass..."; \
		$(PY) scripts/repair_portfolio_gaps.py --type all; \
	fi

validate:
	$(PY) scripts/validate_portfolio_artifacts.py

audit:
	$(PY) scripts/validate_portfolio_artifacts.py --only-logic

select:
	$(PY) scripts/natural_selection.py --top-n $(TOP_N) --threshold $(THRESHOLD)

optimize:
	$(PY) scripts/optimize_portfolio.py

optimize-v2:
	CLUSTER_CAP=0.25 $(PY) scripts/optimize_clustered_v2.py

clustered:
	$(MAKE) optimize-v2

barbell:
	$(PY) scripts/optimize_barbell.py

corr-report:
	mkdir -p $(SUMMARY_DIR)
	$(PY) scripts/correlation_report.py --hrp --out-dir $(SUMMARY_DIR) --min-col-frac 0.2
	$(PY) scripts/analyze_clusters.py

report:
	$(PY) scripts/generate_portfolio_report.py
	$(PY) scripts/generate_audit_summary.py

clean-run: clean-all

	rm -f data/lakehouse/portfolio_*
	$(MAKE) scans
	$(PY) scripts/select_top_universe.py --mode raw
	@echo "--- Pass 1: Lightweight Backfill (60d) for statistical pruning ---"
	CANDIDATES_FILE=data/lakehouse/portfolio_candidates_raw.json $(MAKE) prep BACKFILL=1 GAPFILL=1 LOOKBACK=60 BATCH=5
	$(PY) scripts/audit_antifragility.py
	$(MAKE) select TOP_N=$(TOP_N) THRESHOLD=$(THRESHOLD)
	$(PY) scripts/enrich_candidates_metadata.py
	@echo "--- Pass 2: High Integrity Backfill (200d) for final winners ---"
	$(MAKE) prep BACKFILL=1 GAPFILL=1 LOOKBACK=200 BATCH=2
	$(MAKE) validate
	$(MAKE) corr-report
	$(MAKE) regime-check
	$(MAKE) hedge-anchors
	$(MAKE) drift-check
	$(MAKE) optimize-v2
	$(MAKE) audit
	$(MAKE) report
	$(MAKE) drift-monitor
	$(MAKE) gist
