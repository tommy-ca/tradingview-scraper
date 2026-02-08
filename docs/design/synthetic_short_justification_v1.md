# Audit: Candidate Stream & Synthetic Short Logic (v1)

## 1. Trace: Asset Lifecycle
**Asset**: `BINANCE:XAITRY` (Top Short Winner from `all_short` run `20260124-200353`)

### A. Discovery (Scanner)
- **Source**: `TradingViewDiscoveryScanner`
- **Config**: `binance_spot_rating_all_short`
- **Output**: `{"symbol": "BINANCE:XAITRY", "direction": "SHORT", ...}`
- **Validation**: Debug scan confirmed `SHORT` direction in `data/export/.../candidates.json`.

### B. Consolidation (DataOps)
- **Input**: `candidates.json`
- **Process**: `consolidate_candidates.py`
- **Fix (Phase 1020)**: Added `direction` to `CANONICAL_KEYS`.
- **Output**: `portfolio_candidates.json` confirmed to have `"direction": "SHORT"`.

### C. Selection (HTR)
- **Input**: `portfolio_candidates.json`
- **Process**: `NaturalSelection`
- **Logic**: Preserves direction in winner metadata.
- **Audit**: `audit.jsonl` shows `n_shorts: 15`.

### D. Synthesis (Alpha)
- **Input**: Winner List
- **Process**: `SynthesisStage` -> `StrategySynthesizer`
- **Logic**:
    - Creates Atom: `BINANCE:XAITRY_trend_SHORT_1d`
    - Computes Returns: `atom_rets = generate_atom_returns(...)`
    - **Inversion**: `if direction == "SHORT": atom_rets = -1.0 * atom_rets`
    - **Composition**: `comp_map[atom_id] = {"BINANCE:XAITRY": -1.0}`

### E. Optimization (Risk)
- **Input**: Synthesized Matrix (Inverted Returns)
- **Solver**: `riskfolio` / `skfolio`
- **Constraint**: `weights >= 0` (Long-only solver constraint)
- **Output**: Positive weight assigned to `BINANCE:XAITRY_trend_SHORT_1d` because its inverted returns (which go UP when market goes DOWN) offer diversification benefit.

### F. Flattening (Execution)
- **Input**: Strategy Weights
- **Process**: `flatten_weights`
- **Logic**: `asset_weight = strat_weight * factor (-1.0)`
- **Result**: `BINANCE:XAITRY` has `Net_Weight < 0` (Short Position).

## 2. Evaluation: Synthetic Long Necessity
**Question**: Do we still need to synthesize short portfolios into LONG returns?

**Answer**: **YES, ABSOLUTELY.**

### Rationale
1.  **Solver Compatibility**: Standard convex solvers (Riskfolio, Skfolio, CVXPy default models) are designed to maximize utility functions (Sharpe, Kelly) assuming assets are "things you buy".
    -   If we feed raw *negative* returns (Shorts in a Bull market) to a solver, it will correctly allocate 0% weight (or minimum allowed) because the asset has negative expectancy.
    -   By inverting the returns ($R_{syn} = -R_{raw}$), a losing short position becomes a winning "Synthetic Long" stream. The solver sees positive alpha and allocates capital.
2.  **Constraint Simplicity**: Handling Shorting natively in solvers requires relaxing the `w >= 0` constraint to `w >= -1` (or similar) and managing gross leverage constraints ($|\sum w| \le 1$). This is mathematically complex and error-prone (e.g. "Long-Short" constraints in Riskfolio are often global, not per-asset).
    -   **Synthetic Approach**: We keep the solver in "Long-Only" mode (`0 <= w <= 1`, `sum(w) = 1`). The solver allocates to the "best streams". The *interpretation* of the stream as a physical short happens *post-optimization* during flattening.
3.  **Unified Clustering**: Hierarchical Clustering works best on correlation distance. Inverting the short returns aligns their correlation structure with the portfolio's objective (hedging). Anti-correlated assets become positively correlated *hedges* in the synthetic space if the market crashes.

### Conclusion
The "Synthetic Long" architecture (Pillar 2) is the correct design pattern for this platform. It abstracts directionality from the mathematical risk engine, ensuring robust and stable optimization regardless of market regime.
