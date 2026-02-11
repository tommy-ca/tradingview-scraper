---
date: 2026-02-11
topic: rebalance-vs-stops-unification
---

# Brainstorm: Unifying Rebalance Windows and Discrete Risk Events

## What We're Building
A unified architecture for modeling and executing rebalance windows (Scheduled State) and discrete risk events (SL/TP, Drawdown Guards). This refactor aims to move risk logic out of simulators and into a centralized **Hierarchical Risk Management Engine** that provides consistent behavior across backtesting (VectorBT/Nautilus) and live trading, while strictly enforcing institutional and "Prop Firm" style rules.

## Hierarchical Risk Requirements

### 1. Level 1: Account Guard (Portfolio Sovereignty)
Enforces rules across the entire account balance, regardless of strategy.
- **Max Daily Drawdown (MDD)**: Monitor starting equity of the day. If drawdown exceeds 5% (standard Prop Firm rule), flatten all positions and disable trading for the remainder of the day.
- **Max Total Loss (Equity Guard)**: If total account equity drops below 10% of initial balance, execute a "Full System Shutdown."
- **Daily Risk Quota**: Limit the total notional risk (VaR or Margin) allowed for new entries per 24h cycle.

### 2. Level 2: Correlation Guard (Systemic Risk)
Prevents over-exposure to correlated asset groups.
- **Cluster Exposure Limits**: Utilizing the `VolatilityClusterer` (Pillar 1), cap the total weight of any single cluster (e.g., "AI Tokens" or "Layer 1s") at 25%.
- **Factor Neutrality**: Optional enforcement of Beta-neutrality within the Risk Engine, overriding the allocator if a regime shift occurs intraday.

### 3. Level 3: Order/Asset Guard (Tactical Risk)
Rules applied to individual positions at the point of entry or during monitoring.
- **Kelly Criterion Sizing**: Scale target weights based on the strategy's historical win-rate/payoff ratio (from the `AuditLedger`).
- **Hard Stop Loss (SL)**: Mandatory exit if price hits -1.5% to -5% (asset-specific).
- **Take Profit (TP)**: Discretely triggered exit at fixed targets or via trailing stops.

## Why This Approach
The current "split-brain" architecture leads to several failure modes:
1.  **Re-entry Paradox**: Assets stopped out intraday are immediately re-bought on the next bar because the target state matrix remains non-zero.
2.  **Optimizer Blindness**: Solvers optimize based on raw returns, unaware that execution will truncate the downside.
3.  **Simulation Drift**: Live trading engines (Nautilus) are purely state-driven and lack the "event monitoring" capability present in backtests (VectorBT).
4.  **Regulatory/Prop-Firm Incompatibility**: Current pipelines don't see the "Daily Starting Balance," making it impossible to pass modern trading challenges which rely on "Equity-at-Reset" metrics.

## Proposed Approaches

### Approach 1: The "Pragmatic Sparse" Layer (Data-Driven)
Transition from a dense weight matrix to a **Sparse Instruction Matrix**.
- **Logic**: The `BacktestEngine` emits a row *only* at rebalance points. All other timestamps are `NaN`.
- **Risk Engine**: Resides inside the Simulator. It interprets `NaN` as "Maintain current state, including stopped-out positions."
- **Pros**: 
    - Natively solves the re-entry paradox with VectorBT.
    - Minimal architectural overhead; leverages existing DataFrame-centric patterns.
- **Cons**: Still requires simulators to be "State-Aware" to know that a stop-out persists until the next non-NaN row.

### Approach 2: The "Unified Portfolio Controller" (Agent-Driven)
Introduce a formal **Portfolio Controller** class that sits between the Pipeline and the Simulator.
- **Logic**: The controller manages a state machine for every asset: `POSITIONED`, `STOPPED`, `FLAT`. 
- **Backtesting**: The controller consumes weights and returns, then generates a **high-fidelity trade log** where stops are injected as explicit "Exit" events.
- **Live Trading**: The `NautilusLiveStrategy` *is* the Portfolio Controller. It monitors price and executes the same state transition logic on-exchange.
- **Pros**: 
    - Perfect backtest/live parity. 
    - Allows complex multi-asset stops (e.g., "Stop entire portfolio if total MaxDD > 10%").
- **Cons**: High implementation effort; requires a shared logic layer that works both on vectorized matrices and event streams.

### Approach 3: The "Risk-Wrapped Strategy" (Alpha-Driven)
Move risk logic to Pillar 2 (Synthesis).
- **Logic**: Wrap every atomic strategy (Trend, Reversion) in a **Risk Guard**. The strategy emits **"Stopped Returns"** where the downside is pre-truncated by the SL rule.
- **Optimization**: The `AllocationPipeline` optimizes weights based on these synthetic returns. The solver is now "Risk-Aware."
- **Pros**: 
    - Solves "Optimizer Blindness." 
    - Simulators become simple "Return x Weight" multipliers again.
- **Cons**: Harder to model intraday liquidity or slippage accurately; doesn't solve the "how to execute in live" part directly.

## Prop Firm Rule Synthesis (Benchmarking)

The Risk Management Engine will provide toggleable profiles based on common industry standards:

| Rule Name | Standard Profile (FTMO/E8) | High-Leverage Profile | Rationale |
| :--- | :--- | :--- | :--- |
| **Max Daily Loss** | 5% of starting equity | 3% of starting equity | Prevents "Revenge Trading" and catastrophic tilt. |
| **Max Overall Loss** | 10% of initial balance | 6% of initial balance | Hard stop on account survival. |
| **Asset Cap** | None (implicit) | 20% per Asset | Prevents idiosyncratic risk concentration. |
| **Correlation Cap** | None | 40% per Cluster | Prevents "Single Trade" portfolios hidden by multiple symbols. |

## Key Decisions

- **Decision 1: Modularize Risk**: Extract all SL/TP and Account monitoring logic into a dedicated `tradingview_scraper/risk/engine.py`. This engine should accept both a `pd.DataFrame` (for backtesting) and a `Bar` event (for live).
- **Decision 2: Adopt "Instruction Mode"**: The handoff artifact should change from a "Weight File" to an **"Instruction Ledger"**. A ledger entry contains `(Action, Symbol, Params)`.
- **Decision 3: Hierarchical Validation**: The Risk Engine will run in a "Chain of Responsibility" pattern. Level 1 (Account) must pass before Level 3 (Order) logic is even calculated.
- **Decision 4: State-Persistence**: If an asset is "Stopped," the Risk Engine will flag it as `VETOED` in the `NumericalWorkspace`, preventing the Re-entry Paradox.


## Open Questions
- **Granularity**: How do we align high-resolution stops (e.g. 1m data) with low-resolution rebalances (e.g. 1d data) in a way that remains allocation-efficient?
- **Nautilus Performance**: Will active price monitoring for 500+ symbols in Python introduce latency issues in the event loop?

## Next Steps
→ `/workflows:plan` for implementation:
1. Define the `RebalanceInstruction` and `RiskEvent` Pydantic models.
2. Implement the `RiskManagementEngine` core.
3. Update `VectorBTSimulator` to support the sparse instruction pattern.
