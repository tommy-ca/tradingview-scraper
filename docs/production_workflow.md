# Production Workflow: Discovery → Cluster → Risk → Audit

This runbook documents the institutional "Golden Path" for daily portfolio generation, ensuring data integrity and de-risked asset allocation.

## 1. Automated Execution (Recommended)

The entire lifecycle is unified via the `make clean-run` target. This ensures that every step is executed in the correct sequence with full cleanup of previous artifacts.

```bash
make clean-run
```

**What it does:**
1.  **Wipe**: Clears previous scans and analysis artifacts (`data/lakehouse/portfolio_*`).
2.  **Discover**: Runs multi-asset scanners (Equities, Crypto, Bonds, MTF Forex).
3.  **Enrich**: Captures sectors, industries, and descriptions for all candidates.
4.  **Align (Self-Healing)**: Backfills 200 days of history and automatically repairs identified gaps.
5.  **Cluster**: Builds hierarchical risk buckets and nested sub-clusters for large groups.
6.  **Detect**: Runs the Multi-Factor Regime Detector (Entropy, DWT, Vol Clustering).
7.  **Optimize**: Generates 4 cluster-aware risk profiles with 25% safety caps.
8.  **Audit**: Programmatically verifies all weight caps and Barbell insulation.
9.  **Report**: Produces the prettified implementation dashboard.

---

## 2. Granular Step-by-Step

### Stage 1: Discovery & Metadata
```bash
make scans
uv run scripts/select_top_universe.py
uv run scripts/enrich_candidates_metadata.py
```
- Uses **Alpha Discovery Scoring** (`0.4*Liquidity + 0.4*ADX + 0.2*Vol`) to focus on institutional-grade opportunities.

### Stage 2: Data Alignment (Self-Healing)
```bash
make prep BACKFILL=1 GAPFILL=1 LOOKBACK=200
make validate
```
- Performs a 200-day fetch. `make validate` provides a color-coded health dashboard.
- Automatically triggers `repair_portfolio_gaps.py` to close any internal holes discovered.

### Stage 3: Hierarchical Analysis
```bash
make corr-report
uv run scripts/analyze_clusters.py
uv run scripts/analyze_subcluster.py --cluster 5
```
- Groups 100+ candidates into uncorrelated risk buckets.
- Decomposes large buckets (like the Crypto Hub) into granular venue sub-clusters.

### Stage 4: Risk Optimization & Audit
```bash
make regime-check
make optimize-v2
make audit
```
- Allocates capital across clusters while enforcing a **25% concentration cap**.
- Selects the **Lead Asset** for each cluster using **Alpha Execution Ranking**.
- `make audit` blocks report generation if any risk constraints are breached.

### Stage 5: Implementation Oversight
```bash
make report
make display
```
- `make report`: Generates `summaries/portfolio_report.md` with visual concentration bars.
- `make display`: Opens the interactive terminal dashboard for immediate implementations.
- **Live Output Example**: [GitHub Gist - Portfolio Summaries](https://gist.github.com/tommy-ca/e888e1eab0b86447c90c26e92ec4dc36)

---

## 3. Implementation Guidelines

- **Lead Assets**: Implementation efforts should focus on the designated `Lead Asset` for each cluster to minimize cross-asset noise.
- **Regime Sensitivity**: The Barbell split (90/10) will dynamically adjust to 85/15 in `QUIET` markets or 95/5 in `CRISIS` markets.
- **Fail-Fast**: Never implement a portfolio if `make audit` fails.
