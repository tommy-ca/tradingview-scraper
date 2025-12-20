# Plan: Improve Base Universe Selector with Hybrid Market Cap Guard

This plan outlines the steps to refactor the universe selector to enforce dual-layer market cap guards (Rank-based and Floor-based) while maintaining liquidity as the primary filter.

## Phase 1: Logic Refactor (TDD) [checkpoint: e1c122c]
- [x] Task: TDD - Create `tests/test_universe_selector_guards.py` with failing tests for rank and floor guards
- [x] Task: Update `SelectorConfig` in `tradingview_scraper/futures_universe_selector.py` with `market_cap_rank_limit` and `market_cap_floor`
- [x] Task: Implement hybrid guard logic in `FuturesUniverseSelector._apply_market_cap_filter`
- [x] Task: Verify that `Value.Traded` remains the primary sorting and limiting factor
- [x] Task: Conductor - User Manual Verification 'Logic Refactor' (Protocol in workflow.md)

## Phase 2: Configuration & Integration
- [ ] Task: Update `configs/presets/*.yaml` with the new hybrid guard parameters (e.g., Rank < 200, Floor > $100M)
- [ ] Task: Update exchange-specific `configs/crypto_cex_base_top50_*.yaml` files
- [ ] Task: Rerun `scripts/run_base_scans.sh` to generate new universes
- [ ] Task: Conductor - User Manual Verification 'Configuration & Integration' (Protocol in workflow.md)

## Phase 3: Verification & Reporting
- [ ] Task: Update `scripts/verify_universe_quality.py` to check for both liquidity floor and market cap guards
- [ ] Task: Generate a final report showing the quality and consistency of the selected universes
- [ ] Task: Conductor - User Manual Verification 'Verification & Reporting' (Protocol in workflow.md)
