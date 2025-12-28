# Production Workflow: Discovery → Cluster → Risk → Audit

This runbook documents the institutional "Golden Path" for daily portfolio generation, ensuring data integrity and de-risked asset allocation using a tiered natural selection model.

## 1. Automated Execution (Recommended)

Two execution modes are supported:

### Daily incremental run (recommended for production)
```bash
make daily-run
```
- Runs full multi-asset discovery and the full pipeline.
- Preserves the lakehouse candle cache (`data/lakehouse/*_1d.parquet`) and the last implemented baseline (`data/lakehouse/portfolio_actual_state.json`) for drift monitoring.
- Pushes artifacts to gist before cleanup (archives prior run + validates auth) and again at the final step (`make finalize` includes `make gist`).
- Note: `make prep-raw` includes a best-effort raw health check that may report STALE/MISSING before the first backfill; hard health gates run after the Pass 1 and alignment backfills.

After reviewing (and implementing) the new target weights, snapshot the “last implemented” state:
```bash
make accept-state
```

### Full reset run (use when you want a blank slate)
```bash
make clean-run
```

**What it does:**
1.  **Wipe**: Clears previous scans and analysis artifacts (`data/lakehouse/portfolio_*`).
2.  **Discover**: Runs multi-asset scanners (Equities, Crypto, Bonds, MTF Forex).
3.  **Tiered Selection**: 
    - **Raw Pool**: Aggregates 600+ symbols and merges redundant venues into canonical identities.
    - **Pass 1**: Lightweight 60-day backfill for the raw pool.
    - **Pruning**: Executes **Natural Selection** to filter the universe into ~40 diverse winners.
4.  **Enrich**: Captures sectors, industries, and descriptions for final candidates.
5.  **Align (Self-Healing)**: Performs a deep 200-day backfill and automatically repairs gaps.
6.  **Cluster**: Builds hierarchical risk buckets using **Ward Linkage** and **Intersection Correlation**.
7.  **Detect**: Runs the Multi-Factor Regime Detector (Entropy, DWT, Vol Clustering).
8.  **Optimize**: Generates 4 cluster-aware risk profiles with 25% caps and **Fragility Penalties**.
9.  **Audit**: Programmatically verifies all weight caps and Barbell insulation.
10. **Report**: Produces the prettified implementation dashboard and **Decision Audit Log**.
11. **Sync**: Synchronizes all implementation artifacts to a private GitHub Gist.

---

## 2. Granular Step-by-Step

### Stage 1: Discovery & Canonical Merging
```bash
make scans
uv run scripts/select_top_universe.py --mode raw
```
- Uses **Alpha Discovery Scoring** (`Liquidity + Trend + Vol + Perf`) to rank candidates.
- Merges redundant crypto venues into single economic units with preserved alternative metadata.

### Stage 2: Natural Selection (Pruning)
```bash
make prep BACKFILL=1 GAPFILL=1 LOOKBACK=60
make select TOP_N=3 THRESHOLD=0.4
```
- Performs lightweight statistical pruning to identify the most diverse winners per cluster before deep backfilling.

### Stage 3: High-Integrity Alignment (Self-Healing)
```bash
make prep BACKFILL=1 GAPFILL=1 LOOKBACK=200
make validate
```
- **Selective Sync**: Skips fresh assets to optimize execution speed.
- **Holiday-Aware**: Automatically ignores US market closures (e.g. Thanksgiving, Christmas).

### Stage 4: Risk Optimization & Audit
```bash
make optimize-v2
make audit
```
- **CVaR Penalty**: Mathematically diverts capital from high-fragility sectors.
- **Net vs Gross**: Tracks directional tilt vs total capital at risk.
- **Hybrid Weighting**: Allocates within clusters based on both stability and momentum.

### Stage 5: Implementation Oversight
```bash
make report
make display
make gist
```
- `make report`: Generates `summaries/portfolio_report.md` with visual concentration bars.
- `make display`: Opens the interactive terminal dashboard for immediate implementations.
- `make gist`: Syncs all reports, clustermaps, and audit logs to your private repository; skips sync if `summaries/` is missing/empty (set `GIST_ALLOW_EMPTY=1` to override).
- **Live Output Example**: [GitHub Gist - Portfolio Summaries](https://gist.github.com/tommy-ca/e888e1eab0b86447c90c26e92ec4dc36)

---

## 3. Implementation Guidelines

- **Lead Assets**: Traders should prioritize the designated `Lead Asset` for each cluster.
- **Implementation Alts**: Refer to the "Shared Cluster Reference" for redundant venues if the lead asset lacks liquidity.
- **Decision Trail**: Review `summaries/selection_audit.md` to understand why specific assets were chosen or rejected.
- **Fail-Fast**: Never implement a portfolio if `make audit` fails (Risk logic or Data health breach).
