# Crypto Sleeve Requirements Specification v3.2.14

## 1. Overview

### 1.1 Purpose
Define the institutional requirements for the crypto production sleeve within the multi-sleeve meta-portfolio architecture.

### 1.2 Scope
This specification covers the crypto asset discovery, selection, optimization, and backtesting infrastructure for BINANCE-only production deployment using the `uv` native workflow.

### 1.3 Status
**Production Certified** (2026-01-11) - Metadata Hardened Standard v3.2.14 (Enrichment Fix).

---

## 2. Functional Requirements

### 2.11 Dynamic Regime Adaptation
| Requirement ID | Priority | Status | Description |
|----------------|----------|--------|-------------|
| CR-110 | MUST | ✅ | **Regime Analysis V3**: Analyze returns for Tail Risk (MaxDD, VaR) and Alpha Potential (Momentum, Dispersion). |
| CR-114 | MUST | ✅ | **Alpha Immersion Floor**: The history floor for crypto assets is set to 90 days for production; this maximizes participation of high-momentum listings while maintaining statistical validity. |
| CR-116 | MUST | ✅ | **Antifragility Significance**: Antifragility scores must be weighted by a significance multiplier ($\min(1.0, N/252)$) to prevent low-history assets from dominating the ranking. |
| CR-115 | MUST | ✅ | **Cluster Diversification standard**: The selection engine must pick up to the Top 5 assets per direction (Long/Short) within each cluster to prevent single-asset factor concentration. |
| CR-104 | MUST | ✅ | **Balanced Alpha Selection**: Selection threshold is set to 0.50 with a -0.5 momentum floor to capture high-quality turnaround plays alongside trend leaders. |
| CR-106 | MUST | ✅ | **High-Resolution Factor Isolation**: Clustering distance threshold is set to 0.50 to ensure robust factor separation while allowing for semantic group identification (L1s, AI, Memes). |
| CR-107 | MUST | ✅ | **Native Workflow Enforcement**: All pipeline executions must utilize `uv run` for native dependency resolution and environment isolation. |
| CR-151 | MUST | ✅ | **Four-Stage Refinement Funnel**: Base universes must utilize: 1) 5000-deep Prefetch by raw liquidity; 2) USD-Normalization; 3) Identity Deduplication; 4) Statistical Selection. |
| CR-154 | MUST | ✅ | **Temporal Index Alignment**: Data ingestion and selection layers must enforce `timestamp` indexing to ensure multi-asset data overlap calculations are temporally valid. |
| CR-155 | MUST | ✅ | **Mandatory Metadata Enrichment**: All selection candidates must be enriched with institutional default execution metadata (tick_size, lot_size) prior to risk filtering to prevent technical vetoes for new listings. |
| CR-156 | MUST | ✅ | **Toxic Persistence Veto**: Selection engine must disqualify assets in persistent downtrends (Hurst > 0.55 and Momentum < 0) to protect against "Falling Knives." |
| CR-157 | MUST | ✅ | **Benchmark Exemption**: Macro anchors (SPY) are exempt from Random Walk vetoes to ensure portfolio stability anchors are maintained even in sideways regimes. |
| CR-158 | MUST | ✅ | **Persistence-Aligned Rebalancing**: Rebalancing window ($step\_size$) must be dynamically aligned to the median persistent trend duration (Optimized to 20 days for the current regime). |
| CR-159 | MUST | ✅ | **Secular Shorting Capture**: The discovery layer must include dedicated scanners for structural weakness (`Perf.1M < 0`, `Hurst > 0.50`) to profit from persistent downward drift. |
| CR-160 | MUST | ✅ | **Winner Pool Baseline**: The Selection Engine must target a 15-25% final retention rate (approx. 30 winners from 140 discovered symbols) to ensure sufficient factor representation. |
| CR-161 | MUST | ✅ | **Robust Correlation Standard**: Discovery and clustering must utilize pairwise correlation (Robust Linkage) and a minimum 0.05 column-coverage fraction to prevent "Constituent Collapse." |
| CR-162 | MUST | ✅ | **Matrix Stability Standard**: All portfolio engines must demonstrate bit-perfect determinism across consecutive runs using standardized random seeds (e.g. state=42). |
| CR-163 | MUST | ✅ | **Fallback Transparency**: Portfolio reports must explicitly disclose engine fallbacks when a requested profile (e.g. risk_parity) is not natively supported by the active engine. |
| CR-170 | MUST | ✅ | **Hierarchical Factor Diversity**: The system must utilize Ward Linkage clustering across multiple lookbacks (60d, 120d, 200d) to ensure intra-cluster selection and cluster-level risk capping (25%) are based on stable factor identities. |
| CR-171 | MUST | ✅ | **Cluster Stability Protocol**: Distance matrices must be averaged across windows to reduce sensitivity to transient regime noise, ensuring that orthogonal risk units represent structural market relationships. |
| CR-172 | MUST | ✅ | **Pure Alpha Selection**: The selected candidates universe must exclusively contain assets discovered by scanners; hardcoded benchmarks (SPY) are isolated to baseline profiles unless explicitly selected via the alpha matrix. |
| CR-173 | MUST | ✅ | **Isolation & Enrichment Integrity**: The pipeline must guarantee that metadata enrichment occurs before selection, and benchmark isolation occurs after selection, ensuring no technical vetoes affect valid alpha signals. |

---

**Status**: ✅ All requirements satisfied, validated and hardened for Q1 2026 Production.
