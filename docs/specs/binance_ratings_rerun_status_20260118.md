# Binance Ratings Meta-Portfolio Rerun Status (2026-01-18)

## 1. Execution Summary
**Date**: 2026-01-18  
**Objective**: Full-spectrum production rerun of Binance Rating-Based Meta-Portfolios.
**Standard**: Crypto Sleeve Requirements v3.6.4 (Bi-Weekly 10-day alignment).

## 2. Target Profiles

### 2.1 Atomic Sleeves (Pillar 2)
| Profile | Direction | Status | Run ID |
| :--- | :--- | :--- | :--- |
| `binance_spot_rating_all_long` | LONG | ✅ COMPLETE | `20260118-161253` |
| `binance_spot_rating_all_short` | SHORT | ✅ COMPLETE | `20260118-161504` |
| `binance_spot_rating_ma_long` | LONG | ✅ COMPLETE | `20260118-161655` |
| `binance_spot_rating_ma_short` | SHORT | ✅ COMPLETE | `20260118-161849` |

### 2.2 Meta-Portfolios (Pillar 3)
| Meta Profile | Sleeves | Status |
| :--- | :--- | :--- |
| `meta_benchmark` | All Long + All Short | ✅ COMPLETE |
| `meta_ma_benchmark` | MA Long + MA Short | ✅ COMPLETE |

## 3. Pipeline Stages
- [x] **DataOps**: `make flow-data` (Scans, Ingests, Meta, Features).
- [x] **Discovery**: Execute scanners for all rating-based strategies.
- [x] **Sleeve Execution**: Parallel execution of the 4 atomic production pipelines.
- [x] **Meta-Aggregation**: Recursive return aggregation for `meta_benchmark` and `meta_ma_benchmark`.
- [x] **Optimization**: Hierarchical Risk Parity (HRP) allocation at the meta-level.
- [x] **Flattening**: Collapse meta-weights to physical Binance Spot symbols.
- [x] **Certification**: Generate forensic audit reports.

## 4. Configuration Check
- **Lookback**: 500 days.
- **Training**: 252 days.
- **Step Size**: 10 days (Bi-Weekly).
- **Simulators**: CVXPortfolio, VectorBT.
- **Liquidation Floor**: -100% (CR-660).
- **Cluster Cap**: 25% (CR-590).
