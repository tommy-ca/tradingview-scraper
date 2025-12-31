# Production Workflow: Discovery → Cluster → Risk → Audit

This runbook documents the institutional "Golden Path" for daily portfolio generation, ensuring data integrity and de-risked asset allocation using a tiered natural selection model.

## 1. Automated Execution (Recommended)

The entire production lifecycle is governed by **`configs/manifest.json`** and managed via a typed Python orchestrator, ensuring every run is 100% reproducible and resumable.

### Daily Production Run
```bash
# Run discovery + full 14-step pipeline (Default: production profile)
python -m scripts.run_production_pipeline --profile production

# Resume from Step 12 (Validation) after a timeout or fix
python -m scripts.run_production_pipeline --profile production --start-step 12 --run-id 20251231-180000

# Run with early-access 2026 features enabled
python -m scripts.run_production_pipeline --profile production_v2_canary
```

### Feature Rollout System
The platform uses **Feature Flags** to gradually roll out high-impact quantitative upgrades. These are controlled in the `features` section of the manifest:
- **`feat_turnover_penalty`**: Mathematically reduces rebalancing churn in the custom optimizer.
- **`feat_partial_rebalance`**: Filters out small weight changes (<1%) in the drift monitor.
- **`feat_xs_momentum`**: Uses global percentile ranks for robust leader selection.
- **`feat_spectral_regimes`**: Activates DWT-based `TURBULENT` regime detection and adaptive barbell scaling.
- **`feat_decay_audit`**: Generates high-fidelity slippage decay analysis in final reports.
- **`feat_audit_ledger`**: Enables the cryptographically chained decision ledger.
- **`feat_pit_fidelity`**: Executes production-grade risk auditing during backtest training windows.

**What it does (14-Step Production Sequence):**
1.  **Cleanup**: Wipe previous artifacts (`data/lakehouse/portfolio_*`).
2.  **Discovery**: Run multi-asset scanners (Equities, Crypto, Bonds, MTF Forex).
3.  **Aggregation**: Consolidate scans into a **Raw Pool** with rich metadata preservation.
4.  **Lightweight Prep**: Fetch **60-day** history for the raw pool to establish baseline correlations.
5.  **Natural Selection (Pruning)**: Hierarchical clustering + Global XS Ranking.
6.  **Enrichment**: Propagate sectors, industries, and descriptions.
7.  **High-Integrity Prep**: Fetch **500-day** secular history for winners.
8.  **Health Audit**: Validate 100% gap-free alignment (Automated recovery).
9.  **Factor Analysis**: Build hierarchical risk buckets (Ward Linkage).
10. **Regime Detection**: Multi-factor analysis (Entropy + DWT).
11. **Optimization**: Cluster-Aware allocation with Turnover Control.
12. **Validation**: Walk-Forward "Tournament" benchmarking (High-Fidelity).
13. **Reporting**: QuantStats Tear-sheets + Alpha Isolation Audit.
14. **Audit Verification**: Final cryptographic check of the `audit.jsonl` ledger.

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
