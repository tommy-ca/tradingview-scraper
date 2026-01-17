# Known Issues: Version 3.6.4 (2026-01-16)

## 1. Short Selection Logic Inversion
- **Severity**: **High** (Logic Defect)
- **Component**: `tradingview_scraper/pipelines/selection/stages/policy.py`
- **Description**: The selection policy ranks SHORT candidates in descending order of `alpha_score` (1.0 -> 0.0). Since `alpha_score` is positively correlated with price momentum, this causes the system to select the "Least Bearish" assets (Score ~ 0.001) instead of the "Most Bearish" assets (Score ~ 0.000001).
- **Impact**:
    - `binance_spot_rating_ma_short`: Failed to generate alpha (Sharpe < 0) due to selecting flat assets.
    - `binance_spot_rating_all_short`: Performed well (Sharpe 1.65) likely due to broad beta exposure, but potentially suboptimal alpha capture.
- **Workaround**: None currently applied.
- **Fix Scheduled**: Q2 2026 Sprint (Patch: `reverse=False` for Shorts).

## 2. HRP Numerical Instability
- **Severity**: Medium
- **Component**: `tradingview_scraper/portfolio_engines/risk_parity.py`
- **Description**: HRP optimizer crashes with "Non-finite distance matrix" when the universe contains highly correlated (rho ~ 1.0) or flat-line (zero variance) assets.
- **Impact**: Fallback to `MinVariance` or `EqualWeight` is triggered.
- **Fix Scheduled**: Q2 2026 (Robust Covariance Estimation).

## 3. Missing HHI Metrics
- **Severity**: Low
- **Component**: `scripts/backtest_engine.py`
- **Description**: "Vol-HHI Corr" metric is NaN in reports because simulators do not natively return `top_assets`.
- **Impact**: Reduced observability of concentration risk.
- **Fix Scheduled**: Backlog.
