# Specification: Universe Selection 2.0 (Jan 2026)

This document defines the institutional standard for building the portfolio candidate universe, ensuring survivability and alpha integrity.

## 1. The Triple-Gate Architecture

The pipeline is structured into three mandatory "Hard Gates":

| Gate | Name | Standard | Rationale |
| :--- | :--- | :--- | :--- |
| **Gate 1** | **Forensic Health** | < 5% Gaps, > 320 Days History | Prevents "stale" or "listing-jump" assets from biasing alpha estimates. |
| **Gate 2** | **Composite Selection** | $\text{Score} = \sum (\text{Alpha}, \text{Risk}, \text{Liq})$ | Balanced view of potential return vs. structural fragility. |
| **Gate 3** | **Secular Alignment** | 100% Alignment across 500 days | Ensures covariance matrices are positive-definite and stable. |

## 2. Composite Alpha-Risk Scoring (CARS)

Assets are ranked cross-sectionally using the CARS model:

- **Momentum (40%)**: Unified XS Ranks (60d/120d).
- **Liquidity (20%)**: Standardized Value Traded score.
- **Antifragility (20%)**: Skewness and Tail-Gain score.
- **Defensiveness (20%)**: Inverse CVaR (95%) and Volatility Stability.

## 3. Dynamic Cluster Sizing

The number of winners selected per cluster ($N_c$) scales inversely with cluster density:
$$ N_c = \max(1, \text{round}(\text{base\_n} \times (1 - \rho_{\text{cluster}}))) $$
where $\rho_{\text{cluster}}$ is the mean pairwise correlation. This forces deeper selection in diversified clusters and prevents redundancy in tight ones.

## 4. Implementation Path (14-Step Production Lifecycle)

1.  **Cleanup**: Reset transient state (`make clean-daily`).
2.  **Discovery**: Run multi-engine scanners (`make scan-all`).
3.  **Aggregation**: Build the raw pool with `select_top_universe.py --mode raw`.
4.  **Lightweight Prep**: Fetch 60d history for forensic audit.
5.  **Forensic Risk Audit**: Execute `audit_antifragility.py` (Gate 1 & Gate 2 metrics).
6.  **Natural Selection**: Apply CARS 2.0 filtering with `natural_selection.py`.
7.  **Enrichment**: Add fundamental/metadata context.
8.  **High-Integrity Alignment**: Fetch 500d history for final candidate set.
9.  **Health Audit**: Verify survival through the high-fidelity stretch.
10. **Factor Analysis**: Map clusters and correlations.
11. **Regime Detection**: Switch profiles based on market environment.
12. **Optimization**: Compute final weights via `optimize_clustered_v2.py`.
13. **Validation**: Run backtest tournament.
14. **Reporting & Audit**: Finalize documentation and verify cryptographic ledger.

