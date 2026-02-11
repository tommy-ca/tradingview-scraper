---
title: "feat: Hierarchical Risk Management Engine (Prop Firm Compliance)"
type: feat
date: 2026-02-11
---

# feat: Hierarchical Risk Management Engine (Prop Firm Compliance)

## Enhancement Summary

**Deepened on:** 2026-02-11
**Sections enhanced:** 6
**Review Verdict:** Revision required to reduce "Architecture Astronautics" and harden data structures.

### Key Refinements (Post-Review)
1.  **Flattened Logic**: Replaced the "Chain of Responsibility" pattern with a linear sequence of **Risk Guard Predicates** within a single `RiskPolicy` class.
2.  **Type-Safe Models**: Explicitly defined `RiskContext` and `RiskEvent` Pydantic models. Hardened `Instruction` model with structured `Provenance`.
3.  **Atomic State Management**: Moved away from file-based `.lock` files to a structured `VetoRegistry` (JSON/Stateful) integrated with the existing `AllocationContext`.
4.  **Resilient Snapshotting**: Implemented a "Shadow Snapshot" fallback for the 00:00 UTC reset to handle API downtime and race conditions.

---

## Overview

This plan outlines the architecture and implementation of a centralized **Hierarchical Risk Management Engine**. This engine unifies rebalance windows (Scheduled State) and discrete risk events (SL/TP, Drawdown Guards) into a single supervisor. It strictly enforces institutional-grade "Prop Firm" style rules (e.g., FTMO, E8 Funding) across both backtesting (VectorBT/Nautilus) and live trading.

---

## Proposed Solution: The Risk Policy Guard

Instead of a generic framework, we will implement a focused **RiskPolicy** class that evaluates a sequence of guardrails.

### 1. Level 1: Account Guards (Portfolio Sovereignty)
- **Max Daily Loss (MDD)**: Monitor starting equity at UTC 00:00.
- **Equity Guard**: Hard shutdown if total equity < 90% of initial balance.
- **Daily Risk Quota**: Limit notional risk of new entries.

### 2. Level 2: Correlation Guards (Systemic Risk)
- **Cluster Caps**: Enforce a 25% max weight for any single volatility cluster (Pillar 1).
- **Correlation Veto**: Block entries if EWMA correlation with benchmark > 0.70.

### 3. Level 3: Asset Guards (Tactical Risk)
- **Prop-Firm Kelly Sizing**: Scaled multiplier based on historical win-rates.
- **Discrete Stops**: Strategy-local SL/TP rules.

---

## Technical Approach: Architecture

### 1. Hardened Data Models

```python
class Provenance(BaseModel):
    run_id: str
    strategy_id: str
    regime_id: str

class Instruction(BaseModel):
    symbol: str
    action: Literal["OPEN", "CLOSE", "VETO", "SCALE"]
    target_weight: float
    sl_price: Optional[float]
    tp_price: Optional[float]
    provenance: Provenance

class RiskEvent(BaseModel):
    timestamp: datetime
    trigger: str # e.g., "DAILY_LOSS_LIMIT"
    symbol: Optional[str]
    action: Literal["VETO", "FLATTEN", "SCALE"]
    metadata: Dict[str, Any]
```

### 2. The Veto Registry
To solve the Re-entry Paradox without redundant file I/O, we will use a structured `VetoRegistry` managed within the `BacktestEngine` lifecycle.

```python
class VetoEntry(BaseModel):
    reason: str
    expires_at: Optional[datetime]
    value_at_trigger: float

class VetoRegistry(BaseModel):
    locked_symbols: Dict[str, VetoEntry] = {}
```

---

## Implementation Phases

### Phase 1: Foundation & Modeling (P1)
- [ ] Implement `Provenance`, `Instruction`, and `RiskEvent` models.
- [ ] Implement `RiskContext` for stateful tracking of Daily Starting Equity.
- [ ] Integrate `VetoRegistry` into the `AllocationContext`.

### Phase 2: Risk Guard Implementation (P1)
- [ ] Implement `check_account_mdd` predicate with "Shadow Snapshot" fallback.
- [ ] Implement `check_cluster_caps` using Pillar 1 cluster data.
- [ ] Implement `apply_kelly_scaling` with configurable safety multipliers (e.g., 0.1 for prop).

### Phase 3: Simulator Integration (P2)
- [ ] Refactor `VectorBTSimulator` to consume the `Instruction` sequence.
- [ ] Update `NautilusLiveStrategy` to share the same `RiskPolicy` logic.
- [ ] Ensure "Panic Flattening" includes a `feat_liquidation_penalty`.

### Phase 4: Compliance Suite (P2)
- [ ] Create FTMO/E8 presets in `manifest.json`.
- [ ] Implement `scripts/verify_prop_compliance.py`.

---

## Acceptance Criteria

### Functional Requirements
- [ ] **Paradox Resolved**: Assets hit by SL are correctly flagged in the `VetoRegistry` and skipped until reset.
- [ ] **Snapshot Resilience**: The system can recover the 00:00 UTC baseline from the `AuditLedger` on restart.
- [ ] **Type Safety**: No "stringly-typed" IDs used in the risk-execution bridge.

### Quality Gates
- [ ] **Numerical Parity**: Results match legacy output when risk is disabled.
- [ ] **Performance**: Risk evaluation adds < 50ms latency to the rebalance loop.

