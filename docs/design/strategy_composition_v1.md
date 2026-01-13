# Design Doc: Strategy Composition & Atomic Ensembles (v1.0)

## 1. Concept: The Fundamental Atom
The smallest unit of alpha is a **Fundamental Atom**, defined as:
`Atom = (Asset, AlphaLogic, TimeScale)`

Examples:
- `A1 = (BTCUSDT, Momentum, 1h)`
- `A2 = (ETHUSDT, MeanReversion, 15m)`

## 2. Strategy Composition
A **Complex Strategy** is a weighted composition of Atoms. In the 3-pillar architecture, Pillar 2 (Synthesis) focuses on producing these streams, while Pillar 3 (Allocation) manages the target risk profiles, including market neutrality.

### 2.2 Allocation Responsibility
Market Neutrality is now a **Pillar 3 (Allocation)** responsibility. Instead of pre-composing neutral pairs in the Synthesis layer, the Portfolio Engine is tasked with allocating across synthesized atoms while enforcing beta-neutrality or dollar-neutrality constraints. This allows for more dynamic and global risk management across all active atoms.

## 3. The 3-Pillar Integration

### Pillar 3: Allocation (Decoupled & Hardened)
- **Synthetic Hierarchical Clustering**: The Allocation layer now performs hierarchical clustering on the *synthesized return streams* (Atoms) rather than the raw assets. This identifies uncorrelated alpha clusters in logic-space.
- **Decision-Naive Optimization**: Portfolio engines receive a matrix of strategy returns and optimize according to the requested profile (e.g., `market_neutral`, `max_sharpe`).


## 4. Weight Aggregation (Back-to-Asset)
Final trade execution requires flattening the strategy weights back to the underlying assets:
$$Weight_{Asset,j} = \sum_{Strategies} (Weight_{Strategy,k} \times Weight_{Atom \in Asset_j, k})$$
