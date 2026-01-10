# Crypto Sleeve Requirements Specification v3.1.7

## 1. Overview

### 1.1 Purpose
Define the institutional requirements for the crypto production sleeve within the multi-sleeve meta-portfolio architecture.

### 1.2 Scope
This specification covers the crypto asset discovery, selection, optimization, and backtesting infrastructure for BINANCE-only production deployment.

### 1.3 Status
**Production Certified** (2026-01-10) - Discovery Layer Hardened (CR-151, CR-152).

---

## 2. Functional Requirements

### 2.9 Production Pillars (Forensic Standards)
| Requirement ID | Priority | Status | Description |
|----------------|----------|--------|-------------|
| CR-090 | MUST | ✅ | **Regime Alignment**: Rebalancing frequency must be aligned with the median crypto trend duration ($T_{median} = 19d$) via a 15-day $step\_size$. |
| CR-091 | MUST | ✅ | **Tail-Risk Mitigation**: Max Drawdown must be structurally capped through temporal alignment (Verified 62% reduction via 15d window). |
| CR-092 | MUST | ✅ | **Alpha Capture**: Portfolio entry timing must capture early-cycle momentum ignition for high-beta clusters. |

### 2.10 Optimization Pipeline Standards
| Requirement ID | Priority | Status | Description |
|----------------|----------|--------|-------------|
| CR-100 | MUST | ✅ | **Window Invariance**: Optimization runs must use a fixed 15-day step size to ensure comparability. |
| CR-101 | MUST | ✅ | **Lookahead Standard**: Backtest test windows must be exactly 2x step size (30 days). |
| CR-102 | MUST | ✅ | **Selection Mode Lock**: Crypto production must exclusively use `v3.2` (Log-MPS) for risk engines. |

### 2.11 Dynamic Regime Adaptation
| Requirement ID | Priority | Status | Description |
|----------------|----------|--------|-------------|
| CR-110 | MUST | ✅ | **Regime Analysis V3**: Analyze returns for Tail Risk (MaxDD, VaR) and Alpha Potential (Momentum, Dispersion). |
| CR-111 | MUST | ✅ | **Dynamic Capping**: Adjust optimization cluster caps based on regime: Normal (0.25), Turbulent (0.20), Crisis (0.15). |
| CR-114 | MUST | ✅ | **Alpha Immersion Floor**: The history floor for crypto assets is set to 30 days; selection engine must apply linear significance weighting ($\min(1.0, N/252)$) to these assets. |
| CR-116 | MUST | ✅ | **Antifragility Significance**: Antifragility scores must be weighted by a significance multiplier ($\min(1.0, N/252)$) to prevent low-history assets from dominating the aggressor ranking. |
| CR-115 | MUST | ✅ | **Cluster Diversification standard**: The selection engine must pick up to the Top 3 assets per direction (Long/Short) within each cluster to prevent single-asset factor concentration. |
| CR-151 | MUST | ✅ | **Three-Stage Discovery Funnel**: Base universes must utilize: 1) 5000-deep Prefetch by raw liquidity; 2) Strict Institutional Quote matching (`USDT`, `USDC`, `FDUSD`); 3) Final Top 50 capture. |
| CR-152 | MUST | ✅ | **USD-Normalization Enforcement**: Discovery layers must explicitly filter for institutional quote patterns at the source to prevent non-normalized local fiat pairs (IDR, TRY, ARS) from contaminating the rank. |
| CR-153 | MUST | ✅ | **Adaptive Predictability Gates**: Selection must utilize a 0.05 Efficiency floor and 0.999 Entropy cap for crypto-specific noise tolerance. |

---

## 8. Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-09 | System | Initial production-ready release |
| 1.1 | 2026-01-09 | System | Added staleness and calendar alignment requirements |
| 1.2 | 2026-01-09 | System | Refined staleness thresholds and calendar policy |
| 1.3 | 2026-01-09 | System | Added HRP default and ECI friction requirements |
| 1.4 | 2026-01-09 | System | Added Persistence Research and Window Optimization mandates |
| 1.5 | 2026-01-09 | System | Finalized 15-day rebalancing window based on empirical findings |
| 1.6 | 2026-01-09 | System | Updated with Forensic Audit findings and 3.11 Sharpe validation |
| 1.7 | 2026-01-09 | System | Codified rebalancing frequency as primary tail-risk mitigation |
| 1.8 | 2026-01-09 | System | Final Production Signature with verified Production Pillars |
| 1.9 | 2026-01-09 | System | Hardened Optimization Pipeline standards and version sync |
| 2.0 | 2026-01-09 | System | Added Dynamic Regime Adaptation and advanced analysis metrics |

---

**Status**: ✅ All requirements satisfied and validated
