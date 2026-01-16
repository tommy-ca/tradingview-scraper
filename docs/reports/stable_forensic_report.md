# 🔍 Stable Forensic Audit Report (Phase 176)
**Date:** 2026-01-16 20:06

## 1. Pipeline Funnel Summary
| Run ID | Raw Pool | Selected | Selection Rate |
| :--- | :---: | :---: | :---: |
| `long_all_std` | 16 | 13 | 81.2% |
| `short_all_std` | 10 | 8 | 80.0% |
| `ma_long_std` | 13 | 10 | 76.9% |
| `ma_short_std` | 10 | 8 | 80.0% |
| `ma_long_fast` | 15 | 7 | 46.7% |

## 2. Performance Matrix (Custom Engine)
| Run ID | Profile | Simulator | Sharpe | Total Ret | CAGR | Volatility | MaxDD |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `long_all_std` | equal_weight | cvxportfolio | 11.20 | 15.68X | >100% (Capped) | 8.69 | -31.93% |
| `long_all_std` | hrp | cvxportfolio | 10.07 | 12.96X | >100% (Capped) | 8.46 | -32.12% |
| `long_all_std` | max_sharpe | cvxportfolio | 9.59 | 13.43X | >100% (Capped) | 10.85 | -37.75% |
| `long_all_std` | min_variance | cvxportfolio | 8.82 | 13.23X | >100% (Capped) | 12.15 | -42.42% |
| `short_all_std` | equal_weight | cvxportfolio | -4.97 | -1.37X | 7.42% | 34.86 | -136.54% |
| `short_all_std` | hrp | cvxportfolio | -4.17 | -1.34X | -1.00% | 31.43 | -133.33% |
| `short_all_std` | max_sharpe | cvxportfolio | -1.53 | -1.44X | 7.42% | 175.22 | -142.19% |
| `short_all_std` | min_variance | cvxportfolio | -2.11 | -1.40X | 2.00% | 29.50 | -137.96% |
| `ma_long_std` | equal_weight | cvxportfolio | 12.06 | 16.60X | >100% (Capped) | 8.90 | -33.68% |
| `ma_long_std` | hrp | cvxportfolio | 10.66 | 13.92X | >100% (Capped) | 8.70 | -31.91% |
| `ma_long_std` | max_sharpe | cvxportfolio | 9.93 | 12.44X | >100% (Capped) | 10.74 | -36.31% |
| `ma_long_std` | min_variance | cvxportfolio | 8.89 | 12.02X | >100% (Capped) | 11.63 | -40.33% |
| `ma_short_std` | equal_weight | cvxportfolio | -4.97 | -1.37X | 7.42% | 34.87 | -136.54% |
| `ma_short_std` | hrp | cvxportfolio | -4.18 | -1.34X | -1.00% | 31.30 | -133.33% |
| `ma_short_std` | max_sharpe | cvxportfolio | -1.53 | -1.44X | 7.42% | 174.11 | -142.19% |
| `ma_short_std` | min_variance | cvxportfolio | -2.11 | -1.40X | 2.00% | 29.50 | -137.96% |

## 3. Anomaly Detection (Outliers)
- ⚠️ long_all_std (equal_weight): Extreme Sharpe 11.20
- ⚠️ long_all_std (hrp): Extreme Sharpe 10.07
- ⚠️ long_all_std (max_sharpe): Extreme Sharpe 9.59
- ⚠️ long_all_std (min_variance): Extreme Sharpe 8.82
- ⚠️ short_all_std (equal_weight): Negative Sharpe -4.97 (Expected for Shorts)
- ⚠️ short_all_std (hrp): Negative Sharpe -4.17 (Expected for Shorts)
- ⚠️ short_all_std (min_variance): Negative Sharpe -2.11 (Expected for Shorts)
- ⚠️ ma_long_std (equal_weight): Extreme Sharpe 12.06
- ⚠️ ma_long_std (hrp): Extreme Sharpe 10.66
- ⚠️ ma_long_std (max_sharpe): Extreme Sharpe 9.93
- ⚠️ ma_long_std (min_variance): Extreme Sharpe 8.89
- ⚠️ ma_short_std (equal_weight): Negative Sharpe -4.97 (Expected for Shorts)
- ⚠️ ma_short_std (hrp): Negative Sharpe -4.18 (Expected for Shorts)
- ⚠️ ma_short_std (min_variance): Negative Sharpe -2.11 (Expected for Shorts)