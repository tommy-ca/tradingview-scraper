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
uv run scripts/summarize_results.py | tee summaries/summary_results.txt
uv run scripts/summarize_crypto_results.py | tee summaries/summary_crypto.txt
uv run scripts/correlation_report.py --out-dir summaries  # adds corr regime/pairs/HRP report
```
Outputs: console tables plus saved reports in `summaries/`.

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

### 3.5) Validate Artifacts & Targeted Repair
```
# View full health dashboard
make validate

# Targeted validation
make validate-crypto
make validate-trad

# Targeted repair
make repair-crypto
make repair-trad
```
Checks traceability from candidates to lakehouse and returns matrix. Reports on missing files, stale data, and internal gaps.
- **Smart Logic**: Automatically skips weekend/holiday gaps for non-crypto assets.
- **Statuses**: `OK` (Ready), `OK (MARKET CLOSED)` (Expected gap), `DEGRADED` (Unexpected gap).

### 4) Optimize Portfolios
```
# Modern Portfolio Theory (Standard)
make optimize

# Cluster-Aware Allocation (Groups correlated assets into buckets)
make clustered

# Robust Optimizer (Semi-Variance + Liquidity Penalty)
uv run scripts/optimize_portfolio_robust.py

# Barbell Strategy (Taleb Strategy)
make barbell
```
MPT Profiles: Min Variance, Risk Parity, Max Sharpe.
Clustered: Hierarchical Risk Parity across logical buckets.
Robust: Penalizes illiquid assets and focus on downside risk.
Barbell: 90% Safe Core | 10% Convex Aggressors.

### 5) Full Clean Run
```
make clean-run
```
Automates the entire sequence: Wipe -> Rescan -> Backfill -> Cluster -> Optimize.

### Quick One-Liner (Quick Mode)
```
bash scripts/run_local_scans.sh && bash scripts/run_crypto_scans.sh && \
uv run scripts/summarize_results.py | tee summaries/summary_results.txt && \
uv run scripts/summarize_crypto_results.py | tee summaries/summary_crypto.txt && \
uv run scripts/correlation_report.py --out-dir summaries && \
PORTFOLIO_BATCH_SIZE=5 PORTFOLIO_LOOKBACK_DAYS=100 PORTFOLIO_BACKFILL=0 PORTFOLIO_GAPFILL=0 \
uv run scripts/prepare_portfolio_data.py && \
make validate && \
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
