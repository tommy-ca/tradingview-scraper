# 🔍 Stable Forensic Audit Report (Phase 176)
**Date:** 2026-01-16 12:51

## 1. Pipeline Funnel Summary
| Run ID | Raw Pool | Selected | Selection Rate |
| :--- | :---: | :---: | :---: |
| `long_all_fresh` | 16 | 13 | 81.2% |
| `short_all_fresh` | 10 | 8 | 80.0% |
| `ma_long_fresh` | 13 | 10 | 76.9% |
| `ma_short_fresh` | 10 | 8 | 80.0% |

## 2. Performance Matrix (Custom Engine)
| Run ID | Profile | Simulator | Sharpe | Total Ret | CAGR | Volatility | MaxDD |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `long_all_fresh` | equal_weight | cvxportfolio | 8.48 | 4.94X | >100% (Capped) | 7.10 | -31.92% |
| `long_all_fresh` | hrp | cvxportfolio | 4.91 | 3.42X | 60.89% | 5.82 | -27.64% |
| `long_all_fresh` | max_sharpe | cvxportfolio | 8.21 | 7.79X | >100% (Capped) | 9.81 | -41.20% |
| `long_all_fresh` | min_variance | cvxportfolio | 4.71 | 3.40X | 58.96% | 5.72 | -27.30% |
| `short_all_fresh` | equal_weight | cvxportfolio | -7.71 | -1.22X | -1.00% | 19.68 | -121.55% |
| `short_all_fresh` | hrp | cvxportfolio | -1.76 | -1.08X | -0.99% | 20.58 | -110.67% |
| `short_all_fresh` | max_sharpe | cvxportfolio | -0.77 | -0.98X | -0.98% | 36.76 | -104.48% |
| `short_all_fresh` | min_variance | cvxportfolio | -0.29 | -1.12X | -1.00% | 36.89 | -114.04% |
| `ma_long_fresh` | equal_weight | cvxportfolio | 8.56 | 5.82X | >100% (Capped) | 7.55 | -35.04% |
| `ma_long_fresh` | hrp | cvxportfolio | 7.73 | 5.68X | 91.61% | 6.84 | -31.86% |
| `ma_long_fresh` | max_sharpe | cvxportfolio | 8.38 | 8.87X | >100% (Capped) | 10.20 | -41.62% |
| `ma_long_fresh` | min_variance | cvxportfolio | 5.52 | 5.26X | 70.65% | 7.36 | -32.19% |
| `ma_short_fresh` | equal_weight | cvxportfolio | -7.71 | -1.22X | -1.00% | 19.68 | -121.55% |
| `ma_short_fresh` | hrp | cvxportfolio | -1.76 | -1.08X | -0.99% | 20.58 | -110.67% |
| `ma_short_fresh` | max_sharpe | cvxportfolio | -0.77 | -0.98X | -0.98% | 36.76 | -104.48% |
| `ma_short_fresh` | min_variance | cvxportfolio | -0.29 | -1.12X | -1.00% | 36.89 | -114.04% |

## 3. Anomaly Detection (Outliers)
- ⚠️ long_all_fresh (equal_weight): Extreme Sharpe 8.48
- ⚠️ long_all_fresh (max_sharpe): Extreme Sharpe 8.21
- ⚠️ short_all_fresh (equal_weight): Negative Sharpe -7.71 (Expected for Shorts)
- ⚠️ ma_long_fresh (equal_weight): Extreme Sharpe 8.56
- ⚠️ ma_long_fresh (max_sharpe): Extreme Sharpe 8.38
- ⚠️ ma_short_fresh (equal_weight): Negative Sharpe -7.71 (Expected for Shorts)