# Design Doc: Dynamic Selection Intelligence (v1)

## 1. Problem Statement & Root Cause
The previous "Static Veto" architecture suffered from **Degrees of Freedom (DOF) Mismatch**. While spectral filters (Entropy, Efficiency) were technically correct, their static nature caused "Sparsity Collapse" (n < 4) in early backtest windows or quiet regimes, rendering convex optimization engines (`max_sharpe`, `hrp`) numerically unstable.

### Root Causes
1. **Lookback Truncation**: High-entropy noise caused by calculating 500d metrics on 60d of actual data.
2. **Selection-Solver Decoupling**: Selection logic was unaware of the minimum $N$ required for a stable covariance matrix.
3. **Regime Blindness**: Global thresholds didn't adapt to market-wide volatility compression.

## 2. Proposed Solution: Hierarchical Threshold Relaxation (HTR)
We move from a binary "Veto/Pass" system to a **Multi-Stage Recruitment Funnel**.

### Stage 1: The Golden Filter (Strict)
Apply institutional defaults (e.g., Entropy < 0.995, Efficiency > 0.03). If $N \ge 15$, stop.

### Stage 2: Spectral Relaxation
If $N < 15$, incrementally relax predictability thresholds by 20% (e.g., Entropy < 0.999, Efficiency > 0.01). If $N \ge 15$, stop.

### Stage 3: Clustered Representation (Factor Floor)
If $N$ is still too low, the engine must ensure every significant cluster (determined via Ward linkage) has at least **one** representative asset, regardless of marginal spectral failure. This ensures the optimizer has a "complete map" of the market factor space.

### Stage 4: Alpha-Leader Recruitment (Final Fallback)
If $N < 15$ after Stage 3, recruit the top-ranked assets by `alpha_score` from the rejected pool until $N = 15$.

## 3. Implementation Plan
- **`SelectionEngineV3_3`**: New engine class implementing the HTR loop.
- **`SelectionResponse`**: Updated to include `relaxation_stage` and `active_thresholds` for forensic audit.
- **`Metadata Fallback`**: If `tick_size` or `lot_size` is missing, use exchange-class defaults (e.g., BINANCE_SPOT_DEFAULT) instead of an absolute veto.

## 4. Success Metrics
1. **Solver Success Rate**: 100% (No `nan` or `infeasible` results).
2. **Cluster Coverage**: 100% of non-empty clusters represented in the final selection.
3. **Audit Traceability**: Every recruited asset must be tagged with its recruitment stage in `audit.jsonl`.
