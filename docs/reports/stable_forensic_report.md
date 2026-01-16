# 🔍 Stable Forensic Audit Report (Phase 176)
**Date:** 2026-01-16 11:56

## 1. Pipeline Funnel Summary
| Run ID | Raw Pool | Selected | Selection Rate |
| :--- | :---: | :---: | :---: |
| `long_all_fresh` | 8 | 8 | 100.0% |
| `short_all_fresh` | 4 | 3 | 75.0% |
| `ma_long_fresh` | 7 | 7 | 100.0% |
| `ma_short_fresh` | 4 | 3 | 75.0% |

## 2. Performance Matrix (Custom Engine)
| Run ID | Profile | Simulator | Sharpe | CAGR | Volatility | MaxDD |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| `long_all_fresh` | hrp | cvxportfolio | 6.60 | 100.00% | 8.34% | -33.64% |
| `long_all_fresh` | min_variance | cvxportfolio | 6.57 | 100.00% | 11.90% | -44.05% |
| `long_all_fresh` | max_sharpe | cvxportfolio | 6.57 | 100.00% | 11.90% | -44.05% |
| `long_all_fresh` | equal_weight | cvxportfolio | 7.50 | 100.00% | 8.08% | -30.17% |
| `short_all_fresh` | hrp | cvxportfolio | 0.34 | -1.00% | 14.25% | -113.18% |
| `short_all_fresh` | min_variance | cvxportfolio | 0.34 | -1.00% | 14.25% | -113.18% |
| `short_all_fresh` | max_sharpe | cvxportfolio | 0.34 | -1.00% | 14.25% | -113.18% |
| `short_all_fresh` | equal_weight | cvxportfolio | -0.81 | -1.00% | 10.47% | -109.46% |
| `ma_long_fresh` | hrp | cvxportfolio | 6.60 | 100.00% | 8.34% | -33.64% |
| `ma_long_fresh` | min_variance | cvxportfolio | 6.57 | 100.00% | 11.90% | -44.05% |
| `ma_long_fresh` | max_sharpe | cvxportfolio | 6.57 | 100.00% | 11.90% | -44.05% |
| `ma_long_fresh` | equal_weight | cvxportfolio | 7.50 | 100.00% | 8.08% | -30.17% |
| `ma_short_fresh` | hrp | cvxportfolio | 0.34 | -1.00% | 14.25% | -113.18% |
| `ma_short_fresh` | min_variance | cvxportfolio | 0.34 | -1.00% | 14.25% | -113.18% |
| `ma_short_fresh` | max_sharpe | cvxportfolio | 0.34 | -1.00% | 14.25% | -113.18% |
| `ma_short_fresh` | equal_weight | cvxportfolio | -0.81 | -1.00% | 10.47% | -109.46% |

## 3. Anomaly Detection
✅ No statistical outliers detected.