# Crypto Sleeve Requirements Specification v3.2.4

## 1. Overview

### 1.1 Purpose
Define the institutional requirements for the crypto production sleeve within the multi-sleeve meta-portfolio architecture.

### 1.2 Scope
This specification covers the crypto asset discovery, selection, optimization, and backtesting infrastructure for BINANCE-only production deployment using the `uv` native workflow.

### 1.3 Status
**Production Certified** (2026-01-10) - Balanced Alpha Standard (v3.2.4).

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
| CR-158 | MUST | ✅ | **Persistence-Aligned Rebalancing**: Rebalancing window ($step\_size$) must be dynamically aligned to the median persistent trend duration (Currently 5-15 days). |

---

**Status**: ✅ All requirements satisfied and validated
