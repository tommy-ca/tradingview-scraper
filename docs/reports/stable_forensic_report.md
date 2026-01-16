# 🔍 Stable Forensic Audit Report (Phase 176)
**Date:** 2026-01-16 13:31

## 1. Pipeline Funnel Summary
| Run ID | Raw Pool | Selected | Selection Rate |
| :--- | :---: | :---: | :---: |
| `long_all_fresh` | 17 | 14 | 82.4% |
| `short_all_fresh` | 10 | 8 | 80.0% |
| `ma_long_fresh` | 13 | 10 | 76.9% |
| `ma_short_fresh` | 10 | 8 | 80.0% |

## 2. Performance Matrix (Custom Engine)
| Run ID | Profile | Simulator | Sharpe | Total Ret | CAGR | Volatility | MaxDD |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `long_all_fresh` | equal_weight | cvxportfolio | 11.18 | 14.62X | >100% (Capped) | 8.34 | -31.32% |
| `long_all_fresh` | hrp | cvxportfolio | 7.62 | 13.14X | >100% (Capped) | 7.43 | -34.48% |
| `long_all_fresh` | max_sharpe | cvxportfolio | 8.90 | 15.68X | >100% (Capped) | 10.17 | -38.14% |
| `long_all_fresh` | min_variance | cvxportfolio | 7.58 | 13.11X | >100% (Capped) | 7.43 | -34.51% |
| `short_all_fresh` | equal_weight | cvxportfolio | -7.71 | -1.22X | -1.00% | 19.68 | -121.55% |
| `short_all_fresh` | hrp | cvxportfolio | -1.76 | -1.08X | -0.99% | 20.58 | -110.67% |
| `short_all_fresh` | max_sharpe | cvxportfolio | -0.77 | -0.98X | -0.98% | 36.76 | -104.48% |
| `short_all_fresh` | min_variance | cvxportfolio | -0.29 | -1.12X | -1.00% | 36.89 | -114.04% |
| `ma_long_fresh` | equal_weight | cvxportfolio | 12.19 | 16.71X | >100% (Capped) | 8.77 | -33.69% |
| `ma_long_fresh` | hrp | cvxportfolio | 9.03 | 15.66X | >100% (Capped) | 7.90 | -32.72% |
| `ma_long_fresh` | max_sharpe | cvxportfolio | 9.08 | 16.92X | >100% (Capped) | 10.76 | -39.11% |
| `ma_long_fresh` | min_variance | cvxportfolio | 8.38 | 16.00X | >100% (Capped) | 9.49 | -37.51% |
| `ma_short_fresh` | equal_weight | cvxportfolio | -5.01 | -1.41X | 1.38% | 34.94 | -140.78% |
| `ma_short_fresh` | hrp | cvxportfolio | -1.12 | -1.14X | -1.00% | 41.12 | -116.54% |
| `ma_short_fresh` | max_sharpe | cvxportfolio | -0.93 | -1.09X | -0.99% | 33.63 | -112.92% |
| `ma_short_fresh` | min_variance | cvxportfolio | -0.32 | -1.10X | -1.00% | 49.33 | -112.14% |

## 3. Anomaly Detection (Outliers)
- ⚠️ long_all_fresh (equal_weight): Extreme Sharpe 11.18
- ⚠️ long_all_fresh (max_sharpe): Extreme Sharpe 8.90
- ⚠️ short_all_fresh (equal_weight): Negative Sharpe -7.71 (Expected for Shorts)
- ⚠️ ma_long_fresh (equal_weight): Extreme Sharpe 12.19
- ⚠️ ma_long_fresh (hrp): Extreme Sharpe 9.03
- ⚠️ ma_long_fresh (max_sharpe): Extreme Sharpe 9.08
- ⚠️ ma_long_fresh (min_variance): Extreme Sharpe 8.38
- ⚠️ ma_short_fresh (equal_weight): Negative Sharpe -5.01 (Expected for Shorts)