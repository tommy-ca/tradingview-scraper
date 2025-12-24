# Production Workflow: Scans → Summaries → Portfolio Prep → Optimization

This is the runbook for a daily/production run across scans, summaries, portfolio data prep, and optimizations (MPT and barbell).

## Steps and Commands

### 1) Run Scanners
```
bash scripts/run_local_scans.sh
bash scripts/run_crypto_scans.sh
```
Outputs: `export/universe_selector_*.json` (futures, metals, CFD, forex, US stocks/ETFs, crypto per exchange/type).

### 2) Run Summaries
```
uv run scripts/summarize_results.py
uv run scripts/summarize_crypto_results.py
```
Outputs: console tables; optional to add JSON/CSV if needed.

### 3) Prepare Portfolio Data
```
PORTFOLIO_BATCH_SIZE=5 \
PORTFOLIO_LOOKBACK_DAYS=100 \
PORTFOLIO_BACKFILL=1 \
PORTFOLIO_GAPFILL=1 \
uv run scripts/prepare_portfolio_data.py
```
Inputs: `data/lakehouse/portfolio_candidates.json` (from selectors).
Outputs: `data/lakehouse/portfolio_returns.pkl`, logs of any dropped/missing symbols.
Knobs: set `BACKFILL/GAPFILL` to 0 for a quick run; caps are enforced in the script.

### 4) Optimize Portfolios
```
uv run scripts/optimize_portfolio.py
```
Profiles: Min Variance, Risk Parity, Max Sharpe. Output: `data/lakehouse/portfolio_optimized.json`.

### 5) Barbell (Taleb-style)
```
uv run scripts/optimize_barbell.py
```
Output: `data/lakehouse/portfolio_barbell.json` (core + aggressors).

### Quick One-Liner (Quick Mode)
```
bash scripts/run_local_scans.sh && bash scripts/run_crypto_scans.sh && \
uv run scripts/summarize_results.py && uv run scripts/summarize_crypto_results.py && \
PORTFOLIO_BATCH_SIZE=5 PORTFOLIO_LOOKBACK_DAYS=100 PORTFOLIO_BACKFILL=0 PORTFOLIO_GAPFILL=0 \
uv run scripts/prepare_portfolio_data.py && \
uv run scripts/optimize_portfolio.py && \
uv run scripts/optimize_barbell.py
```

## Data Quality & Checks
- Ensure returns matrix has sufficient history: drop symbols with too few days; log them.
- Validate weights: no NaNs/inf; weights ~ sum to 1; report top allocations.
- Monitor counts per exchange in crypto summaries; expect heavy short skew currently.
- Backfill/gapfill caps are set to avoid huge pulls; increase only when needed.

## Index Lists (US Bases)
- `scripts/update_index_lists.py` builds SP500/Nasdaq100 lists from slickcharts/ETF/wiki; outputs to `data/index/sp500_symbols.txt`, `.../nasdaq100_symbols.txt`.
- Bases consume these lists via `include_symbol_files` (see `configs/us_stocks_base_universe.yaml`, `configs/us_etf_base_universe.yaml`).

## Operational Notes
- Use `uv run` to stay within the project environment.
- Logs: capture step logs if running in automation; abort on non-zero exit.
- If scanner/summary output is empty for a market, rerun or check rate limits.
- For faster iterations, set `PORTFOLIO_BACKFILL=0` and `PORTFOLIO_GAPFILL=0`.
