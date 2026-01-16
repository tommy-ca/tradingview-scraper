# 🔍 Stable Forensic Audit Report (Phase 176)
**Date:** 2026-01-16 12:04

## 1. Pipeline Funnel Summary
| Run ID | Raw Pool | Selected | Selection Rate |
| :--- | :---: | :---: | :---: |
| `long_all_fresh` | 8 | 8 | 100.0% |
| `short_all_fresh` | 4 | 3 | 75.0% |
| `ma_long_fresh` | 7 | 7 | 100.0% |
| `ma_short_fresh` | 4 | 3 | 75.0% |

## 2. Performance Matrix (Custom Engine)
| Run ID | Profile | Simulator | Sharpe | Total Ret | CAGR | Volatility | MaxDD |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `long_all_fresh` | equal_weight | cvxportfolio | 8.90 | 11.53X | >100% (Capped) | 10.98 | -42.53% |
| `long_all_fresh` | hrp | cvxportfolio | 8.16 | 8.07X | >100% (Capped) | 9.17 | -37.22% |
| `long_all_fresh` | max_sharpe | cvxportfolio | 7.00 | 6.30X | >100% (Capped) | 9.64 | -39.09% |
| `long_all_fresh` | min_variance | cvxportfolio | 7.06 | 6.35X | >100% (Capped) | 9.55 | -38.74% |
| `short_all_fresh` | equal_weight | cvxportfolio | -0.49 | -0.98X | -1.00% | 16.99 | -103.29% |
| `short_all_fresh` | hrp | cvxportfolio | nan | -1.17X | -1.00% | nan | -115.02% |
| `short_all_fresh` | max_sharpe | cvxportfolio | nan | -1.17X | -1.00% | nan | -115.02% |
| `short_all_fresh` | min_variance | cvxportfolio | nan | -1.17X | -1.00% | nan | -115.02% |
| `ma_long_fresh` | equal_weight | cvxportfolio | 8.99 | 13.00X | >100% (Capped) | 11.52 | -43.51% |
| `ma_long_fresh` | hrp | cvxportfolio | 8.89 | 13.89X | >100% (Capped) | 11.48 | -43.92% |
| `ma_long_fresh` | max_sharpe | cvxportfolio | 8.68 | 13.62X | >100% (Capped) | 11.36 | -44.04% |
| `ma_long_fresh` | min_variance | cvxportfolio | 8.69 | 13.62X | >100% (Capped) | 11.37 | -44.06% |
| `ma_short_fresh` | equal_weight | cvxportfolio | -0.49 | -0.98X | -1.00% | 16.99 | -103.29% |
| `ma_short_fresh` | hrp | cvxportfolio | nan | -1.17X | -1.00% | nan | -115.02% |
| `ma_short_fresh` | max_sharpe | cvxportfolio | nan | -1.17X | -1.00% | nan | -115.02% |
| `ma_short_fresh` | min_variance | cvxportfolio | nan | -1.17X | -1.00% | nan | -115.02% |

## 3. Anomaly Detection (Outliers)
- ⚠️ long_all_fresh (equal_weight): Extreme Sharpe 8.90
- ⚠️ long_all_fresh (hrp): Extreme Sharpe 8.16
- ⚠️ ma_long_fresh (equal_weight): Extreme Sharpe 8.99
- ⚠️ ma_long_fresh (hrp): Extreme Sharpe 8.89
- ⚠️ ma_long_fresh (max_sharpe): Extreme Sharpe 8.68
- ⚠️ ma_long_fresh (min_variance): Extreme Sharpe 8.69