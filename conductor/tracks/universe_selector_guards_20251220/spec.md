# Spec: Improve Base Universe Selector with Hybrid Market Cap Guard

## Overview
This track aims to refine the `FuturesUniverseSelector` to prioritize liquidity (`Value.Traded`) while enforcing a strict "Market Cap Guard." This hybrid guard will use an external file for rank-based filtering (Top N) and real-time screener data for an absolute market cap floor, ensuring the resulting universe consists only of high-quality, high-capacity assets.

## Objectives
- Implement a dual-layer Market Cap Guard:
    - **Guard A (Rank-based):** Only include symbols that appear in the Top N (e.g., Top 200) of the external `market_caps_crypto.json`.
    - **Guard B (Floor-based):** Enforce an absolute minimum market cap (e.g., > $500M) using real-time `market_cap_calc` from TradingView.
- Maintain `Value.Traded` as the primary importance filter for liquidity.
- Improve the `FuturesUniverseSelector` logic to handle this hybrid guard efficiently.
- Verify that the resulting base universes meet both liquidity and market cap quality standards.

## Functional Requirements
- **Selector Refactor:** Update `FuturesUniverseSelector` to:
    - Load and rank assets from `market_cap_file`.
    - Apply the "Rank Guard" (Top N) during the `_apply_post_filters` stage.
    - Apply the "Floor Guard" ($ minimum) using the `market_cap_calc` column.
- **Config Updates:** Update YAML configs to specify `market_cap_rank_limit` (e.g., 200) and `market_cap_floor` (e.g., 500,000,000).
- **Liquidity Priority:** Ensure `value_traded_min` remains the most critical filter for inclusion in the final limited universe.
- **State Validation:** Verify that the "Guard" logic doesn't inadvertently shrink the universe below the desired count if liquidity is otherwise high.

## Acceptance Criteria
- [ ] `FuturesUniverseSelector` correctly implements the Hybrid Market Cap Guard.
- [ ] Base universes generated only contain assets within the specified Top N rank AND above the dollar floor.
- [ ] Final universe is sorted and limited based on the existing liquidity (`Value.Traded`) and count rules.
- [ ] Verification report shows assets meet both Guard A and Guard B criteria across all exchanges.
