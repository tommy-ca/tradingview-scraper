# Audit Report: Meta-Portfolio Pipeline (v2)

**Date**: 2026-01-23
**Meta Profile**: `meta_benchmark_audit`
**Run ID**: `meta_benchmark_audit_20260123-162024`

## 1. Executive Summary
This audit validated the Fractal Meta-Portfolio construction using verified atomic runs (`long_all`, `short_all`). The pipeline successfully aggregated returns, optimized allocations, and flattened weights into physical positions.

**Status**: 🟡 **PASSED WITH FINDINGS** (Pipeline functional, Semantic defect detected)

## 2. Meta-Level Data Contracts
| Layer | Contract | Status | Evidence |
| :--- | :--- | :--- | :--- |
| **L0** | **Meta-Returns** | ✅ PASS | `meta_returns_*.pkl` generated with correct dimensions. |
| **L1** | **Health Guard** | ✅ PASS | 100% solver health detected for atomic sleeves. |
| **L4** | **Meta-Allocation** | ✅ PASS | Meta-weights sum to 1.0. Allocation (50/50 for EW) respected. |
| **L4** | **Physical Flattening** | ✅ PASS | Recursive flattening conserved total weight mass. |

## 3. Forensic Findings

### 3.1 Return Stitching
- Successfully stitched returns from `binance_spot_rating_all_long` and `binance_spot_rating_all_short`.
- **Correction**: Required manual re-run of `backtest_engine.py` with explicit `TV_PROFILE` to generate missing return artifacts (Nautilus vs VectorBT configuration drift).

### 3.2 Directional Semantics (CRITICAL)
- **Observation**: The `short_all` sleeve (`binance_spot_rating_all_short`) produced **positive** Net Weights in the flattened meta-portfolio.
- **Root Cause**: The atomic run produced `LONG` direction atoms despite the profile having `feat_short_direction: true`.
- **Impact**: The "Short" sleeve is effectively acting as a "Long" sleeve, neutralizing the hedge intent of the Benchmark.
- **Trace**:
    - Atomic Selection: `Winner BINANCE:CHZUSDT Direction: LONG`
    - Atomic Synthesis: Atom name likely `..._LONG`
    - Meta Flattening: `Net_Weight: 0.1` (Positive)

### 3.3 Artifact Integrity
- `meta_optimized_*.json`: Created and valid.
- `meta_cluster_tree_*.json`: Created and valid (Fractal lineage preserved).
- `portfolio_optimized_meta_*.json`: Created and valid.

## 4. Recommendations
1.  **Fix Short Logic**: Investigate `StrategySynthesizer` and `DiscoveryPipeline` to ensure `binance_spot_rating_all_short` correctly flags assets as `SHORT` or inverts returns.
2.  **Backtest Output Guard**: Update `backtest_engine.py` to always save return artifacts even if a simulator crashes, or fail fast.
3.  **Meta-Manifest Trace**: Explicitly log the `manifest.json` used during meta-runs to ensure reproducibility of profile definitions.

## 5. Conclusion
The Meta-Portfolio orchestration logic is sound and robust. The L0-L4 contracts are enforcing numerical stability. However, a semantic configuration error in the `Short` profile needs immediate remediation to restore hedging properties.
