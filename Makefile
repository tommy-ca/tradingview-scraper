SHELL := /bin/bash
PY ?= uv run
BATCH ?= 5
LOOKBACK ?= 100
BACKFILL ?= 1
GAPFILL ?= 1
SUMMARY_DIR ?= summaries

.PHONY: help update-indexes clean-exports scans-local scans-crypto scans summaries reports validate prep optimize barbell corr-report pipeline pipeline-quick

help:
	@echo "Make targets:"
	@echo "  make update-indexes      # refresh SP500/NDX lists"
	@echo "  make clean-all           # remove export/ and summaries/"
	@echo "  make scans               # run local + crypto scanners"
	@echo "  make summaries           # run summarizers"
	@echo "  make validate            # validate portfolio artifacts"
	@echo "  make prep               # prepare portfolio data"
	@echo "  make optimize            # run MPT optimizers"
	@echo "  make clustered           # run Cluster-aware optimizer"
	@echo "  make barbell             # run Taleb barbell optimizer"
	@echo "  make corr-report         # correlation/HRP report"
	@echo "  make clean-run           # Full pipeline from scratch"
	@echo "  make pipeline            # Full production pipeline"

update-indexes:
	$(PY) scripts/update_index_lists.py

clean-exports:
	rm -f export/*.json

clean-summaries:
	rm -rf $(SUMMARY_DIR)/*

clean-all: clean-exports clean-summaries
	@echo "All exports and summaries cleaned."

scans-local:
	bash scripts/run_local_scans.sh

scans-crypto:
	bash scripts/run_crypto_scans.sh

scans: scans-local scans-crypto

summaries:
	mkdir -p $(SUMMARY_DIR)
	$(PY) scripts/summarize_results.py | tee $(SUMMARY_DIR)/summary_results.txt
	$(PY) scripts/summarize_crypto_results.py | tee $(SUMMARY_DIR)/summary_crypto.txt

validate:
	$(PY) scripts/validate_portfolio_artifacts.py

validate-crypto:
	$(PY) scripts/validate_portfolio_artifacts.py --type crypto

validate-trad:
	$(PY) scripts/validate_portfolio_artifacts.py --type trad

repair-crypto:
	$(PY) scripts/repair_portfolio_gaps.py --type crypto

repair-trad:
	$(PY) scripts/repair_portfolio_gaps.py --type trad

prep:
	PORTFOLIO_BATCH_SIZE=$(BATCH) PORTFOLIO_LOOKBACK_DAYS=$(LOOKBACK) PORTFOLIO_BACKFILL=$(BACKFILL) PORTFOLIO_GAPFILL=$(GAPFILL) \
	$(PY) scripts/prepare_portfolio_data.py

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

reports: summaries corr-report

pipeline: scans summaries prep corr-report optimize barbell

pipeline-quick:
	$(MAKE) pipeline BACKFILL=0 GAPFILL=0

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
	$(MAKE) report
