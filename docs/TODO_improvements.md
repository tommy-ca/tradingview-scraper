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

## 4. Crypto Refinement
- [ ] **Unified "Liquid" Presets:** Refactor remaining per-exchange crypto configs (OKX, Bybit, Bitget) to use the `crypto_cex_preset_binance_top50_perp.yaml` pattern (or create a generic `crypto_liquid_perp.yaml`).
