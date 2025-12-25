# Production Workflow: Discovery → Cluster → Risk → Audit

This runbook documents the daily production cycle, ensuring high-integrity data alignment and de-risked asset allocation using hierarchical clusters.

## 1. Automated Execution (Recommended)

The entire pipeline is unified via the `make clean-run` target. This is the institutional default for generating new portfolios.

```bash
make clean-run
```

**What it does:**
1.  **Wipe**: Clears previous scans and analysis artifacts (`data/lakehouse/portfolio_*`).
2.  **Discover**: Runs scanners for Equities, Crypto, Bonds, and MTF Forex.
3.  **Align**: Backfills 200 days of historical data and aligns the returns matrix.
4.  **Cluster**: Builds hierarchical risk buckets and nested sub-clusters for venue redundancy.
5.  **Detect**: Runs the Advanced Regime Detector (Entropy, DWT, Vol Clustering).
6.  **Optimize**: Generates 4 cluster-aware risk profiles (Min Var, RP, Sharpe, Barbell).
7.  **Audit**: Programmatically verifies all weight caps and insulation constraints.
8.  **Report**: Generates the prettified dashboard at `summaries/portfolio_report.md`.

---

## 2. Granular Step-by-Step

### Stage 1: discovery & metadata
```bash
make scans
uv run scripts/select_top_universe.py
uv run scripts/enrich_candidates_metadata.py
```
- **Goal**: Identify secular long/short candidates and capture sector/industry context.

### Stage 2: Data preparation
```bash
make prep BACKFILL=1 GAPFILL=1 LOOKBACK=200
make validate
```
- **Goal**: Ensure 100% gap-free history for all 100+ candidates. `make validate` provides a color-coded health dashboard.

### Stage 3: Hierarchical Analysis
```bash
make corr-report
uv run scripts/analyze_clusters.py
uv run scripts/analyze_subcluster.py --cluster 5  # Zoom into Crypto Hub
```
- **Goal**: group highly correlated assets (e.g. 70+ crypto tickers) into single units of risk.

### Stage 4: Risk Optimization & Audit
```bash
make regime-check
make optimize-v2
make audit
```
- **Goal**: Allocate across clusters with a **25% concentration cap**. `make audit` enforces weight normalization and Barbell insulation.

### Stage 5: Decision Support
```bash
make report
```
- **Goal**: Produce the professional Markdown dashboard with asset-class grouping and visual concentration bars.

---

## 3. Data Quality & Guards

- **Gap Mitigation**: The pipeline automatically skips weekend/holiday gaps for non-crypto assets.
- **Venue Neutrality**: Nested sub-clustering prevents venue-specific noise from biasing systemic risk.
- **Fail-Fast Audit**: If a profile breaches the 25% cap or insulation rule, the `make audit` gate will block report generation.

## 4. Operational Controls

- **Lookback**: Default is 200 days for robust correlation.
- **Batching**: Use `BATCH=2` during backfills to avoid TradingView rate limits.
- **Regime Tuning**: Scoring thresholds can be adjusted in `tradingview_scraper/regime.py`.
