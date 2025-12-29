# Planned Improvements for Universe Selector

## 1. Strategy Expansion
- [ ] **Short Mean Reversion:** Create configurations to identify overbought assets in a downtrend (Selling Rips).
    - [ ] Futures
    - [ ] US Stocks
    - [ ] Forex
    - [ ] Crypto

## 2. Advanced Filtering Logic
- [ ] **Cross-Sectional (XS) Momentum:** Implement logic to filter based on relative performance (e.g., Top 10% of universe by 3M return) rather than absolute thresholds.
    - Requires script updates to support percentile-based post-filtering.

## 3. Workflow Enhancements
- [ ] **"Confirmed" vs "Active" Signals:** Update scan scripts to output two lists:
    - **Active:** Triggered execution filters (e.g., Daily Change < 0.2%).
    - **Watchlist:** "Confirmed" setup but waiting for trigger (e.g., ignoring daily change).
- [ ] **Sector/Industry Analysis:**
    - [ ] Add `sector` and `industry` columns to US Stocks preset.
    - [ ] Create scans to rank sectors by momentum.

## 5. Portfolio Risk & Optimization Engines
- [ ] **Multi-Engine Integration:** Implement standard `BaseRiskEngine` interface for third-party libraries.
    - [ ] **skfolio:** Integrate HRP and Max Diversification.
    - [ ] **Riskfolio-Lib:** Integrate CVaR and Tail Risk optimization.
    - [ ] **PyPortfolioOpt:** Integrate MVO with shrinkage.
    - [ ] **CVXPortfolio:** Integrate Multi-Period Optimization (MPO).
- [ ] **Optimization Benchmarking:** 
    - [ ] Update `BacktestEngine` with "Tournament Mode" for side-by-side comparison.
    - [ ] Generate comparative reports across all 4 profiles (MinVar, HRP, MaxSharpe, Barbell).
