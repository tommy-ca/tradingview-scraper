# Specification: Immutable Audit Ledger (V1)
**Status**: Draft / Proposed
**Date**: 2025-12-31

## 1. Overview
This document defines the requirements and design for the **Immutable Audit Ledger**, a system designed to ensure 100% reproducibility and cryptographic integrity of the quantitative production pipeline. It moves the platform from passive logging to an active "Decision Ledger" that links every output to its specific input data and configuration.

## 2. Core Requirements

### 2.1 Write-Ahead Logging (WAL) Principle
Every significant pipeline step must record its **Intent** (Inputs + Parameters) before execution and its **Outcome** (Results + Artifact Hashes) after completion.

### 2.2 Cryptographic Chaining
- Log entries must be chained using SHA-256 hashes.
- Each record must contain a `prev_hash` field referencing the hash of the previous line.
- The `hash` of the current record is calculated over the entire JSON content + the `prev_hash`.

### 2.3 Deterministic Data Hashing
- The system must implement a standardized way to hash Pandas DataFrames (`df_hash`).
- Hashes must be stable across different environments (ignoring non-essential metadata like internal memory addresses).

### 2.4 Persistence
- The ledger is stored as a JSON-Lines file (`audit.jsonl`) within the run-scoped artifact directory.
- A "Genesis Block" must be created at the start of every run, capturing the environment (Git SHA, Python Version, Manifest Hash).

## 3. Data Schema

### 3.1 Genesis Block
```json
{
  "type": "genesis",
  "run_id": "20251231-150000",
  "ts": "2025-12-31T15:00:00Z",
  "env": {
    "git_sha": "a1b2c3d...",
    "python_v": "3.12.x",
    "manifest_hash": "sha256..."
  },
  "hash": "..."
}
```

### 3.2 Action Entry
```json
{
  "type": "action",
  "step": "optimization",
  "status": "intent|success|failure",
  "intent": {
    "params": { "profile": "risk_parity" },
    "input_hashes": { "returns": "sha256..." }
  },
  "outcome": {
    "output_hashes": { "weights": "sha256..." },
    "metrics": { "objective_value": 0.042 }
  },
  "prev_hash": "...",
  "hash": "..."
}
```

### 3.3 Backtest Window Entry
```json
{
  "type": "action",
  "step": "backtest_window",
  "status": "success",
  "meta": {
    "window_start": "2023-01-01",
    "window_end": "2023-01-20",
    "engine": "custom",
    "profile": "max_sharpe"
  },
  "intent": {
    "input_hashes": { "train_returns": "sha256..." }
  },
  "outcome": {
    "output_hashes": { "window_weights": "sha256...", "test_returns": "sha256..." },
    "metrics": { "realized_sharpe": 1.4, "turnover": 0.12 }
  },
  "prev_hash": "...",
  "hash": "..."
}
```

## 4. Pipeline Integration Points

| Stage | Audit Evidence Captured |
| :--- | :--- |
| **Discovery** | Count of symbols found per market, Hash of raw candidate list. |
| **Pruning** | Hash of 60d returns matrix, rationale for cluster exclusions. |
| **Alignment** | Count of gap-filled candles, Hash of final 500d returns matrix. |
| **Optimization** | Solver convergence status, individual cluster weights, turnover cost. |
| **Tournament** | Per-window hashes of training slices and realized returns. |

## 5. Verification
A standalone utility `scripts/verify_ledger.py` will be provided to:
1. Recompute the hash chain to detect tampering.
2. Verify that the current `data/lakehouse` artifacts match the hashes recorded in the ledger.
3. Report any "unexplained" deviations in the implementation universe.
