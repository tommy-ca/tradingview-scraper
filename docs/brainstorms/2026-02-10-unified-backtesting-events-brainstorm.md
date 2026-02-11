---
date: 2026-02-10
topic: unified-backtesting-events
---

# Unified Backtesting: Rebalance Windows as Discrete Events

## What We're Building
A unified architecture for backtesting that treats rebalance windows and stop rules (SL/TP) as discrete, pushed events rather than polled states. This unification will bridge the gap between weight-based simulators (VectorBT, Custom) and event-driven engines (Nautilus), while solving the "Re-entry Paradox" identified in previous audits.

## Why This Approach
The current "split-brain" architecture uses a state-map (`target_weights` DataFrame) that simulators poll on every bar. This leads to:
1.  **Re-entry Paradox**: Assets stopped out intraday are immediately re-bought on the next bar because the state-map still indicates a non-zero target weight.
2.  **Architectural Fragmentation**: VectorBT uses a continuous matrix, while Nautilus polls in backtesting but watches files in live.
3.  **Simulation Inconsistency**: Stop rules are only supported in VectorBT, making cross-engine validation unreliable.

By modeling rebalancing as a discrete **`RebalanceEvent`**, we can push instructions only when they change, allowing simulators to manage their own internal state (including stops) until the next event arrives.

## Proposed Approaches

### Approach A: The Sparse Event Matrix (VBT-Centric / Pragmatic)
In this approach, the `BacktestEngine` generates a sparse weight matrix where `NaN` represents "no action" and values represent "rebalance to this %".
- **Pros**: 
    - Native compatibility with VectorBT's `from_orders` API.
    - Resolves the Re-entry Paradox: if an asset is stopped out, it remains at zero until the next non-NaN row in the weight matrix.
- **Cons**: Still relies on a DataFrame-centric model, which is slightly less idiomatic for high-fidelity event engines like Nautilus.

### Approach B: The Unified Event Bus (Nautilus-Centric / Architectural)
Define a formal `Event` hierarchy (`RebalanceEvent`, `StopEvent`) that both simulators consume.
- **Pros**:
    - Perfect parity between backtest and live (Nautilus already uses this for live).
    - Allows complex, multi-asset stop logic (e.g., "Stop if total portfolio MaxDD > 10%").
- **Cons**: Requires a more significant refactor of the `VectorBTSimulator` to translate the event stream into its required matrix format.

## Key Decisions
- **Decision 1: Event-Driven Source**: Use a **Scheduler** (derived from `WalkForwardOrchestrator`) that emits a `RebalanceEvent` at the start of each window.
- **Decision 2: Stop Ownership**: simulators (VBT, Nautilus) will monitor and trigger their own stops based on a shared configuration provided in the `RebalanceEvent`.
- **Decision 3: Unification Layer**: The `SimulationStage` will act as the "Event Dispatcher," converting the pipeline's output into the appropriate event format for each backend.

## Open Questions
- **Granularity**: Should we support intraday rebalance events, or only window-start events? (Recommendation: Start with window-start for YAGNI).
- **VBT Versioning**: Does our current `vectorbt` version support the complex re-entry logic required for Approach A natively?

## Next Steps
→ `/workflows:plan` for implementation details:
1.  Define the `RebalanceEvent` and `SimulationContext` Pydantic models.
2.  Refactor `VectorBTSimulator` to use sparse matrix rebalancing.
3.  Implement `on_rebalance` in `NautilusRebalanceStrategy`.
