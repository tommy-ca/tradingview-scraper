# 🔍 Stable Forensic Audit Report (Phase 176)
**Date:** 2026-01-16 11:39

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
| `short_all_fresh` | hrp | cvxportfolio | 6.34 | 100.00% | 11.49% | -46.22% |
| `short_all_fresh` | min_variance | cvxportfolio | 6.34 | 100.00% | 11.49% | -46.22% |
| `short_all_fresh` | max_sharpe | cvxportfolio | 6.34 | 100.00% | 11.49% | -46.22% |
| `short_all_fresh` | equal_weight | cvxportfolio | 5.39 | 100.00% | 6.69% | -35.33% |
| `ma_long_fresh` | hrp | cvxportfolio | 6.60 | 100.00% | 8.34% | -33.64% |
| `ma_long_fresh` | min_variance | cvxportfolio | 6.57 | 100.00% | 11.90% | -44.05% |
| `ma_long_fresh` | max_sharpe | cvxportfolio | 6.57 | 100.00% | 11.90% | -44.05% |
| `ma_long_fresh` | equal_weight | cvxportfolio | 7.50 | 100.00% | 8.08% | -30.17% |
| `ma_short_fresh` | hrp | cvxportfolio | 6.34 | 100.00% | 11.49% | -46.22% |
| `ma_short_fresh` | min_variance | cvxportfolio | 6.34 | 100.00% | 11.49% | -46.22% |
| `ma_short_fresh` | max_sharpe | cvxportfolio | 6.34 | 100.00% | 11.49% | -46.22% |
| `ma_short_fresh` | equal_weight | cvxportfolio | 5.39 | 100.00% | 6.69% | -35.33% |

## 3. Anomaly Detection
✅ No statistical outliers detected.