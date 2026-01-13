# Design Doc: Directional Synthetic Logic (v1.0)

## 1. Context & Objective
Quantitative optimization engines (Convex Solvers) are mathematically designed to find optimal positive weights for positive expected returns. Handling `SHORT` directions requires a transformation that aligns "Price Decline" with "Positive Alpha."

## 2. Synthetic Long Normalization
We implement **Synthetic Long Normalization** to allow direction-naive solvers to handle short-biased strategies.

### 2.1 The Transformation
Before the returns matrix is passed to any `BaseRiskEngine`, assets tagged with `direction: SHORT` undergo return inversion:
$$R_{syn} = -1 \times R_{raw}$$

### 2.2 Numerical Impact
1. **Positive Expected Return**: A falling asset ($R_{raw} < 0$) produces a positive synthetic return ($R_{syn} > 0$), making it attractive to the solver.
2. **Covariance Stability**: Inverting returns preserves the variance but flips the sign of the covariance relative to other assets. This correctly identifies the short position as a diversifier or hedge.
3. **Constraint Integrity**: The solver operates in a "Long-Only" space (weights $\ge 0$), which is significantly more stable than allowing negative weights in 3rd party libraries.

## 3. Realization & Mapping
While the solver sees a "Long" position, the backtest simulator and implementation layer must map this back to the physical asset.

### 3.1 Weight Reporting
- **Synthetic Weight ($W_{syn}$)**: The weight returned by the solver (always $\ge 0$).
- **Net Weight ($W_{net}$)**: 
  - If Direction = LONG: $W_{net} = W_{syn}$
  - If Direction = SHORT: $W_{net} = -1 \times W_{syn}$

### 3.2 Realized Return Calculation
The backtest simulator must calculate PnL using the raw returns and net weights:
$$PnL = W_{net} \times R_{raw}$$
By substitution:
$$PnL = (-1 \times W_{syn}) \times R_{raw} = W_{syn} \times (-1 \times R_{raw}) = W_{syn} \times R_{syn}$$
This proves that optimizing on synthetic long returns is mathematically equivalent to shorting the raw asset.

## 4. Risks & Mitigations
- **Borrow Costs**: Shorting incurs costs. These must be modeled as a drag on $R_{syn}$ prior to optimization.
- **Reporting Confusion**: Audit logs must clearly distinguish between $W_{syn}$ and $W_{net}$ to prevent "Inverse Exposure" hallucinations during forensic review.
