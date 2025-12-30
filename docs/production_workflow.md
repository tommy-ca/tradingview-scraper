# Production Workflow: Discovery → Cluster → Risk → Audit

This runbook documents the institutional "Golden Path" for daily portfolio generation, ensuring data integrity and de-risked asset allocation using a tiered natural selection model.

## 1. Automated Execution (Recommended)

Two execution modes are supported:

### Daily incremental run (recommended for production)
```bash
# Optional config preflight (recommended after editing configs)
make scan-lint

# Primary entry point (uses configs/manifest.json 'production' profile)
make run-daily

# Use lightweight dev profile for fast validation
make run-daily PROFILE=repro_dev

# Optional metadata gates (build + audit catalogs before portfolio run)
make run-daily META_REFRESH=1 META_AUDIT=1
```
- Runs full multi-asset discovery and the full pipeline.
- Preserves the lakehouse candle cache (`data/lakehouse/*_1d.parquet`) and the last implemented baseline (`data/lakehouse/portfolio_actual_state.json`) for drift monitoring.
- Pushes artifacts to gist before cleanup (publishes last successful run + validates auth) and again at the final step (`make finalize` publishes the current run and then promotes `artifacts/summaries/latest`).
- Note: `make prep-raw` includes a best-effort raw health check that may report STALE/MISSING before the first backfill; hard health gates run after the Pass 1 and alignment backfills.

After reviewing (and implementing) the new target weights, snapshot the “last implemented” state:
```bash
make accept-state
```

### Full reset run (use when you want a blank slate)
```bash
make clean-run
```

**What it does (13-Step Production Sequence):**
1.  **Cleanup**: Wipe previous artifacts (`data/lakehouse/portfolio_*`).
2.  **Discovery**: Run multi-asset scanners (Equities, Crypto, Bonds, MTF Forex).
3.  **Aggregation**: Consolidate scans into a **Raw Pool** with canonical identity merging (Venue Neutrality).
4.  **Lightweight Prep**: Fetch **60-day** history for the raw pool to establish baseline correlations.
5.  **Natural Selection (Pruning)**: Hierarchical clustering on the raw pool; select **Top 3 Assets** per cluster using **Execution Intelligence**.
6.  **Enrichment**: Propagate sectors, industries, and descriptions to the filtered winners.
7.  **High-Integrity Prep**: Fetch **200-day** secular history for winners with automated gap-repair.
8.  **Health Audit**: Validate 100% gap-free alignment for the implementation universe (Triggers `make recover` if gaps found).
9.  **Factor Analysis**: Build hierarchical risk buckets using **Ward Linkage** and **Adaptive Thresholds**.
10. **Regime Detection**: Multi-factor analysis (**Entropy + DWT Spectral Turbulence**).
11. **Optimization**: Cluster-Aware V2 allocation with **Fragility (CVaR) Penalties**, supported by a multi-engine benchmarking framework (`skfolio`, `Riskfolio`, `PyPortfolioOpt`, `cvxportfolio`).
12. **Validation**: Run `make tournament` to benchmark multiple optimization backends against the custom baseline.
13. **Reporting**: Generate Implementation Dashboard, Strategy Resume, and sync to private Gist.


---

## 2. Granular Step-by-Step

### Stage 1: Discovery & Canonical Merging
```bash
make scan-lint  # validate configs first
make scan-all   # alias: make scans
make prep-raw   # builds raw candidates + best-effort raw health check
```
- Uses **Alpha Discovery Scoring** (`Liquidity + Trend + Vol + Perf`) to rank candidates.
- Merges redundant crypto venues into single economic units with preserved alternative metadata.

#### Optional: Forex Base Universe Audit
```bash
# Fast: liquidity report only
RUN_ID=$(date +%Y%m%d-%H%M%S) make forex-analyze-fast

# Full: backfill + gap-fill + data health + clusters
RUN_ID=$(date +%Y%m%d-%H%M%S) make forex-analyze
```
- Excludes IG-only singleton pairs by default; outputs land in `artifacts/summaries/runs/<RUN_ID>/` (see `forex_universe_report.md` and `forex_universe_data_health.csv`).

### Stage 2: Natural Selection (Pruning)
```bash
make prune TOP_N=3 THRESHOLD=0.4  # pass-1 backfill + health gate + natural selection
```
- Performs lightweight statistical pruning to identify the most diverse winners per cluster before deep backfilling.

### Stage 3: High-Integrity Alignment (Self-Healing)
```bash
make align LOOKBACK=200           # deep backfill + selected-mode health gate
make audit-logic                  # logic checks (recommended)

# Or full validation (includes backtests)
make validate
```
- **Selective Sync**: Skips fresh assets to optimize execution speed.
- **Holiday-Aware**: Automatically ignores US market closures (e.g. Thanksgiving, Christmas).

### Data Quality Gates
The pipeline includes an automated **Step 8: Health Audit & Automated Recovery**. 
- If gaps are detected in the implementation universe, `make recover` is triggered automatically.
- Recovery includes intensive gap repair and a matrix alignment refresh.
- If `STRICT_HEALTH=1` is set (default in `production` profile), the run will fail if any gaps remain after recovery.

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
- `make report`: Generates `artifacts/summaries/runs/<RUN_ID>/portfolio_report.md` with visual concentration bars (available via `artifacts/summaries/latest/portfolio_report.md` after a successful finalize).
- `make display`: Opens the interactive terminal dashboard for immediate implementations.
- `make gist`: Syncs all reports, clustermaps, and audit logs from `artifacts/summaries/latest/` (symlink to last successful finalized run) to your private repository; skips sync if missing/empty (set `GIST_ALLOW_EMPTY=1` to override).
- **Live Output Example**: [GitHub Gist - Portfolio Summaries](https://gist.github.com/tommy-ca/e888e1eab0b86447c90c26e92ec4dc36)

---

## 3. Implementation Guidelines

- **Lead Assets**: Traders should prioritize the designated `Lead Asset` for each cluster.
- **Implementation Alts**: Refer to the "Shared Cluster Reference" for redundant venues if the lead asset lacks liquidity.
- **Decision Trail**: Review `artifacts/summaries/latest/selection_audit.md` (last successful finalized run) to understand why specific assets were chosen or rejected.
- **Fail-Fast**: Never implement a portfolio if `make audit` fails (Risk logic or Data health breach).
