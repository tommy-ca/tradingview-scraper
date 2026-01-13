# Specification: Strategy Synthesis & Atomic Composition (v1.1)

## 1. Objective
Enable the platform to compose complex strategies (Long/Short, Market Neutral) from fundamental atomic units of alpha.

## 2. Fundamental Atom
An **Atom** is the smallest indivisible return stream.
`Atom = (Asset, Logic, TimeScale)`

### 2.1 Standard Atoms
- **Momentum**: `Signal = sign(TrailingReturn_N)`
- **Mean Reversion**: `Signal = -sign(Price - MA_N)`
- **Trend Follow**: `Signal = 1 if Price > MA_Slow else 0`

## 3. Composition Standard (Complex Strategies)
A Strategy is a collection of Atoms with internal weights.

### 3.1 Long/Short Pair Strategy
`S = (Atom_A_Long, Atom_B_Short)`
Weights: `w_A = 1.0, w_B = -1.0`
Result: $R_S = R_A - R_B$

### 3.2 Market Neutral Ensemble
`S = (Asset_Alpha_Atom, Benchmark_Hedge_Atom)`
Result: $R_S = R_{Alpha} - \beta \times R_{Benchmark}$
Where $\beta$ is dynamically calculated per window.

## 4. Synthesis Lifecycle
1. **Selection**: Pillar 1 identifies high-quality candidates.
2. **Atomization**: Pillar 2 generates raw atom return streams.
3. **Composition**: Joins atoms into complex strategy streams.
4. **Normalization**: Applies Synthetic Long Normalization to ensure $R_{strategy}$ is positive-alpha biased.

## 6. Baseline Selection Workflow
The `baseline` selection engine receives the **complete raw universe** (L1 candidates) and passes it through without any spectral or momentum filtering. This serves as the 'Control Group' for quantifying the Alpha Value Added by advanced HTR filters.
- **Workflow**: Completes Pillar 1 by returning all raw assets as winners.
- **Allocation**: Pillar 3 performs hierarchical clustering on the full pool to ensure HRP and other clustered solvers have a valid baseline risk structure.
