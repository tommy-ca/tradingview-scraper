# Production Workflow: Discovery → Cluster → Risk → Audit

This runbook documents the institutional "Golden Path" for daily portfolio generation, ensuring data integrity and de-risked asset allocation using a tiered natural selection model.

## 1. Automated Execution (Recommended)

The entire production lifecycle is governed by **`configs/manifest.json`**, ensuring every run is 100% reproducible.

### Daily Production Run
```bash
# Run discovery + full 13-step pipeline (Default: production profile)
make daily-run

# Run a lightweight development smoke-test
make daily-run PROFILE=repro_dev

# Optional: Refresh and audit metadata catalogs before the run
make daily-run META_REFRESH=1 META_AUDIT=1
```

**What it does (13-Step Production Sequence):**
1.  **Cleanup**: Wipe previous artifacts (`data/lakehouse/portfolio_*`).
2.  **Discovery**: Run multi-asset scanners (Equities, Crypto, Bonds, MTF Forex).
3.  **Aggregation**: Consolidate scans into a **Raw Pool** with canonical identity merging (Venue Neutrality).
4.  **Lightweight Prep**: Fetch **60-day** history for the raw pool to establish baseline correlations.
5.  **Natural Selection (Pruning)**: Hierarchical clustering on the raw pool; select **Top 3 Assets** per cluster using **Execution Intelligence**.
6.  **Enrichment**: Propagate sectors, industries, and descriptions to the filtered winners.
7.  **High-Integrity Prep**: Fetch **500-day** secular history for winners with automated gap-repair.
8.  **Health Audit**: Validate 100% gap-free alignment for the implementation universe (Triggers `make recover` if gaps found).
9.  **Factor Analysis**: Build hierarchical risk buckets using **Ward Linkage** and **Adaptive Thresholds**.
10. **Regime Detection**: Multi-factor analysis (**Entropy + DWT Spectral Turbulence**).
11. **Optimization**: Cluster-Aware V2 allocation with **Fragility (CVaR) Penalties**, supported by a multi-engine benchmarking framework (`skfolio`, `Riskfolio`, `PyPortfolioOpt`, `cvxportfolio`).
12. **Validation**: Run `make tournament` to benchmark multiple optimization backends across idealized and high-fidelity simulators (200d realized target).
13. **Reporting**: Generate QuantStats Markdown Tear-sheets, Strategy Resume, and sync essential artifacts to private Gist.

---

## 2. Decision Logic & Specifications

### Data Quality Gates
The pipeline includes an automated **Step 8: Health Audit & Automated Recovery**. 
- If gaps are detected in the implementation universe, `make recover` is triggered automatically.
- Recovery includes intensive gap repair and a matrix alignment refresh.
- If `strict_health: true` is set in the manifest, the run will fail if any gaps remain after recovery.

### Immutable Market Baseline
The framework treats the market benchmark as a first-class **"Market" Engine**.
- **Strategy**: 100% Long `AMEX:SPY`.
- **Integrity**: Loaded directly from raw lakehouse data, bypassing scanner-specific direction flipping.

### Execution Alpha Decay
The "Tournament" evaluates an `Engine x Simulator` matrix to quantify the performance lost to friction.
- **Idealized**: Zero-friction returns (theoretical alpha).
- **Realized**: High-fidelity simulation including 5bps slippage and 1bp commission.

---

## 3. Implementation Oversight

### Strategy Dashboards
- **Strategy Resume (`backtest_comparison.md`)**: Unified dashboard pulling the realizable baseline from the tournament matrix.
- **Tournament Benchmark (`engine_comparison_report.md`)**: Comparative benchmark of all optimization engines.
- **Detailed Analytics**: High-density QuantStats Markdown reports with monthly matrices and drawdown audits.
- **Live Output Example**: [GitHub Gist - Portfolio Summaries](https://gist.github.com/e888e1eab0b86447c90c26e92ec4dc36)

### Implementation Guidelines
- **Golden Artifact Selection**: Only the most critical ~32 reports are pushed to the Gist to maintain high signal-to-noise ratio.
- **Fail-Fast**: Never implement a portfolio if `make audit` fails (Risk logic or Data health breach).
