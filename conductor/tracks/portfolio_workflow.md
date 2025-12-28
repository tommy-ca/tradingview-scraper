# Portfolio Workflow (Scans → Prep → Optimize)

This playbook shows the end-to-end steps: run local + crypto scanners, summarize outputs, prep portfolio data, rank/build the universe, and optimize across profiles (min variance, risk parity à la Ray Dalio, and antifragile barbell à la Taleb).

## 1) Run scanners
```
# Recommended: run-scoped exports
RUN_ID=20251228-120000 make scan-all

# Or run individual groups
TV_EXPORT_RUN_ID=20251228-120000 bash scripts/run_local_scans.sh
TV_EXPORT_RUN_ID=20251228-120000 bash scripts/run_crypto_scans.sh
```
- Outputs land in `export/<run_id>/` as `universe_selector_*` JSONs using a `{meta,data}` envelope.

## 2) Summarize scan results
```
# Defaults to the newest `export/<run_id>/` if TV_EXPORT_RUN_ID is unset
TV_EXPORT_RUN_ID=20251228-120000 uv run scripts/summarize_results.py
TV_EXPORT_RUN_ID=20251228-120000 uv run scripts/summarize_crypto_results.py
```
- Produces console summaries for all asset classes.

## 3) Prepare portfolio data (fetch/backfill/gap-fill + returns)
```
# Tune batch/limits as needed; backfill/gapfill capped with timeouts/limits
PORTFOLIO_BATCH_SIZE=5 \
PORTFOLIO_LOOKBACK_DAYS=100 \
PORTFOLIO_BACKFILL=1 \
PORTFOLIO_GAPFILL=0 \
uv run scripts/prepare_portfolio_data.py
```
- Env knobs: `PORTFOLIO_BATCH_SIZE`, `PORTFOLIO_LOOKBACK_DAYS`, `PORTFOLIO_BACKFILL`, `PORTFOLIO_GAPFILL` (set 0 to skip backfill/gapfill).
- **Stabilization Note:** Backfill and Gap-fill now have strict caps (120s backfill timeout, 60s gap-fill timeout, 2010 legacy cutoff). If the script hangs or takes too long, set `PORTFOLIO_GAPFILL=0`.
- Uses `data/lakehouse/portfolio_candidates.json` (built from selectors) and writes `data/lakehouse/portfolio_returns.pkl` plus sidecar metadata.

## 4) Rank/build universe for portfolio
- Universe comes from `data/lakehouse/portfolio_candidates.json` (produced by the selectors + `select_top_universe.py`).
- `prepare_portfolio_data.py` loads prices/returns for those candidates; check the summary logs for any symbols dropped due to missing history.

## 5) Optimize portfolios (multiple profiles)
```
uv run scripts/optimize_portfolio.py
```
Profiles currently emitted by `optimize_portfolio.py`:
- **Minimum Variance**
- **Risk Parity** (equal risk contribution; Ray Dalio style)
- **Maximum Sharpe**

For an antifragile/barbell take (Taleb style), run the dedicated barbell script:
```
uv run scripts/optimize_barbell.py
```
(Configure inside the script as needed for barbell splits.)

## Quick daily sequence
```
RUN_ID="$(date +%Y%m%d-%H%M%S)"; export RUN_ID; export TV_EXPORT_RUN_ID="$RUN_ID"; \
make scan-all && \
uv run scripts/summarize_results.py && uv run scripts/summarize_crypto_results.py && \
PORTFOLIO_BATCH_SIZE=5 PORTFOLIO_LOOKBACK_DAYS=100 PORTFOLIO_BACKFILL=1 PORTFOLIO_GAPFILL=1 \
uv run scripts/prepare_portfolio_data.py && \
uv run scripts/optimize_portfolio.py
```
- Adjust batch/lookback/backfill flags per run. Skip backfill/gapfill by setting the env vars to 0 for faster iterations.
