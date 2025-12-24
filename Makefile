SHELL := /bin/bash
PY ?= uv run
BATCH ?= 5
LOOKBACK ?= 100
BACKFILL ?= 1
GAPFILL ?= 1
SUMMARY_DIR ?= summaries

.PHONY: help update-indexes clean-exports scans-local scans-crypto scans-bonds scans summaries reports validate prep optimize barbell corr-report pipeline pipeline-quick audit report clean-run

scans-bonds:
	$(PY) -m tradingview_scraper.bond_universe_selector --config configs/bond_etf_trend_momentum.yaml --export json

scans-forex-mtf:
	$(PY) -m tradingview_scraper.cfd_universe_selector --config configs/forex_mtf_monthly_weekly_daily.yaml --export json

scans: scans-local scans-crypto scans-bonds scans-forex-mtf


summaries:
	mkdir -p $(SUMMARY_DIR)
	$(PY) scripts/summarize_results.py | tee $(SUMMARY_DIR)/summary_results.txt
	$(PY) scripts/summarize_crypto_results.py | tee $(SUMMARY_DIR)/summary_crypto.txt

validate:
	$(PY) scripts/validate_portfolio_artifacts.py

audit:
	$(PY) scripts/validate_portfolio_artifacts.py --only-logic

optimize:
	$(PY) scripts/optimize_portfolio.py

optimize-v2:
	CLUSTER_CAP=0.25 $(PY) scripts/optimize_clustered_v2.py

clustered:
	$(PY) scripts/optimize_portfolio_clustered.py

barbell:
	$(PY) scripts/optimize_barbell.py

corr-report:
	mkdir -p $(SUMMARY_DIR)
	$(PY) scripts/correlation_report.py --hrp --out-dir $(SUMMARY_DIR) --min-col-frac 0.2

report:
	$(PY) scripts/generate_portfolio_report.py

clean-run: clean-all
	rm -f data/lakehouse/portfolio_*
	$(MAKE) scans
	$(PY) scripts/select_top_universe.py
	$(MAKE) prep BACKFILL=1 GAPFILL=1 LOOKBACK=200
	$(MAKE) validate
	$(MAKE) corr-report
	$(PY) scripts/audit_antifragility.py
	$(MAKE) optimize-v2
	$(MAKE) audit
	$(MAKE) report

