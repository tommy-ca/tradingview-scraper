SHELL := /bin/bash
PY ?= uv run
BATCH ?= 5
LOOKBACK ?= 100
BACKFILL ?= 1
GAPFILL ?= 1
SUMMARY_DIR ?= summaries

.PHONY: help update-indexes clean-exports scans-local scans-crypto scans summaries prep optimize barbell corr-report pipeline pipeline-quick

help:
	@echo "Make targets:"
	@echo "  make update-indexes      # refresh SP500/NDX lists"
	@echo "  make clean-exports       # remove export/*.json"
	@echo "  make scans               # run local + crypto scanners"
	@echo "  make summaries           # run summarizers (also saved under $(SUMMARY_DIR)/)"
	@echo "  make prep               # prepare portfolio data (use BATCH/LOOKBACK/BACKFILL/GAPFILL)"
	@echo "  make optimize            # run MPT optimizers"
	@echo "  make barbell             # run Taleb barbell optimizer"
	@echo "  make corr-report         # correlation/HRP report to $(SUMMARY_DIR)"
	@echo "  make pipeline            # scans -> summaries -> prep -> corr-report -> optimize -> barbell"
	@echo "  make pipeline-quick      # same as pipeline, but BACKFILL=0 GAPFILL=0"

update-indexes:
	$(PY) scripts/update_index_lists.py

clean-exports:
	rm -f export/*.json

scans-local:
	bash scripts/run_local_scans.sh

scans-crypto:
	bash scripts/run_crypto_scans.sh

scans: scans-local scans-crypto

summaries:
	mkdir -p $(SUMMARY_DIR)
	$(PY) scripts/summarize_results.py | tee $(SUMMARY_DIR)/summary_results.txt
	$(PY) scripts/summarize_crypto_results.py | tee $(SUMMARY_DIR)/summary_crypto.txt

prep:
	PORTFOLIO_BATCH_SIZE=$(BATCH) PORTFOLIO_LOOKBACK_DAYS=$(LOOKBACK) PORTFOLIO_BACKFILL=$(BACKFILL) PORTFOLIO_GAPFILL=$(GAPFILL) \
	$(PY) scripts/prepare_portfolio_data.py

optimize:
	$(PY) scripts/optimize_portfolio.py

barbell:
	$(PY) scripts/optimize_barbell.py

corr-report:
	mkdir -p $(SUMMARY_DIR)
	$(PY) scripts/correlation_report.py --out-dir $(SUMMARY_DIR)

pipeline: scans summaries prep corr-report optimize barbell

pipeline-quick:
	$(MAKE) pipeline BACKFILL=0 GAPFILL=0
