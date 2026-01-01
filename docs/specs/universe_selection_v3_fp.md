# Specification: Universe Selection 3.0 (Darwinian Selection & MPS)

## 1. Foundational Axioms & Theoretical Grounding

1.  **Ergodicity & The Absorbing Barrier (Darwinian Survival)**: 
    - **Axiom**: Survival is the only prerequisite. 
    - **Evolutionary Analogy**: Selection precedes fitness. An organism that doesn't reach reproductive age has a fitness of zero.
    - **Implementation**: **Survival Veto Gate**. Assets with `P(Survival) < 0.1` are disqualified regardless of alpha.
    
2.  **Multiplicative Risk (Lethal Mutations)**:
    - **Axiom**: High performance cannot compensate for structural failure.
    - **Evolutionary Analogy**: Essential organs are a "Series System." Failure of the heart (Liquidity) cannot be offset by stronger legs (Alpha).
    - **Implementation**: **Multiplicative Probability Scoring (MPS)**. Total score is the product of component probabilities.

3.  **Information-Theoretic Connectivity (Niche Differentiation)**:
    - **Axiom**: Information overlap is the leading indicator of shared risk.
    - **Evolutionary Analogy**: Species in the same niche (shared risk drivers) compete for the same resources and are vulnerable to the same extinctions.
    - **Implementation**: **Hierarchical Clustering + Numerical Stability Gate**.

## 2. Requirement: The Darwinian Health Gate (Extinction Testing)
- **Definition**: Assets must prove "Data Integrity" during specific **Stress Events**.
- **Threshold**: `Regime_Survival_Score >= 0.1`.
- **Logic**: Absolute veto if missing history or failed stress test.

## 3. Requirement: Multiplicative Probability Scoring (MPS 3.0)
- **Model**: $S_{total} = P_{momentum} \times P_{stability} \times P_{antifragility} \times P_{liquidity} \times P_{survival}$
- **Mapping Methods**:
    - **Alpha Components** (Momentum, Stability, Antifragility): mapped via **Percentile Rank** to $[0.01, 1.0]$.
    - **Health/Execution Components** (Survival, Liquidity): mapped via **Absolute CDF** to $[0.001, 1.0]$.
- **Goal**: Hard-veto of fragile or illiquid assets via near-zero multiplication.

## 4. Requirement: Downstream Engine Alignment (The Continuity Gate)

1.  **Numerical Stability (Numerical Stability Gate)**:
    - **Metric**: **Condition Number ($\kappa$)** of the return covariance matrix.
    - **Constraint**: $\kappa < 10^6$. 
    - **Action**: If $\kappa \ge 10^6$, the system triggers **Aggressive Pruning**, restricting selection to exactly 1 winner per cluster to eliminate redundant highly-correlated assets.

2.  **Transaction Cost Awareness (Estimated Cost of Implementation - ECI)**:
    - **Logic**: Use the **Square-Root Impact Model**: $Cost = \sigma \sqrt{\frac{OrderSize}{ADV}}$.
    - **Constraint**: $Annualized\_Alpha - ECI > 0.02$ (2% net alpha floor).
    - **Veto**: Assets failing this net alpha test are disqualified.

3.  **Metadata Completeness**:
    - **Metric**: **Instrument Definition Parity**.
    - **Requirement**: `tick_size`, `lot_size`, and `price_precision` must be present and valid. 
    - **Veto**: Any symbol lacking execution metadata is disqualified.

## 5. Modular Architecture (Selection Engines)

Selection logic is abstracted into versioned engines:
- **SelectionEngineV3 (MPS 3.0)**: Current institutional standard. Implements all 3.0 vetoes and multiplicative scoring.
- **SelectionEngineV2 (CARS 2.0)**: Composite Alpha-Risk Scoring. Uses additive weighted ranks.
- **LegacySelectionEngine (V1.0)**: Original local normalization within clusters.

## 7. Profile Differentiation (Darwinian vs. Robust)

The V3 engine behavior is modulated by the selected profile, allowing for tuning the "Strictness" of the Darwinian gates.

### 7.1 Stability Gates ($\kappa$)
- **Darwinian Strictness**: Forces aggressive pruning (1 winner per cluster) at $\kappa \ge 10^6$. This ensures near-perfect numerical stability for sensitive solvers like `cvxpy`.
- **Robust Strictness**: Extends the limit to $\kappa \ge 10^7$, allowing for more asset redundancy in clusters where slight collinearity is acceptable for the sake of diversification.

### 7.2 Execution Gates (ECI)
- **Darwinian ECI**: Strictly enforces the $Annualized\_Alpha - ECI > 0.02$ net floor.
- **Robust ECI**: Disables the hard ECI gate, allowing high-turnover alpha assets to remain in the universe for experimental validation in low-friction simulators (e.g., ReturnsSimulator).

Every selection run records a "Decision Block" in the **Immutable Audit Ledger**. In the **Tournament Framework**, these metrics are used to quantify the "Selection Alpha" and the implementation efficiency of the V3 engine.

### 6.1 Performance Feedbacks
- **Selection Alpha Isolation**: The tournament compares the V3 Filtered universe against the Raw Discovery Pool to measure the efficacy of the MPS scoring.
- **Stability Audit**: The Condition Number ($\kappa$) is logged per-window. The system correlates $\kappa$ with portfolio optimization failures to validate the $10^6$ threshold.
- **Cost Preservation**: The ECI (Estimated Cost of Implementation) gate is validated by comparing the realized slippage in high-fidelity simulators against the ECI predictions.

### 6.2 Decision Context
- **Veto Trace**: Detailed reasons per symbol (e.g., "Survival Gate < 0.1", "ECI Penalty") are committed to the ledger.
- **Component Probabilities**: Individual $P_{momentum}$, $P_{survival}$, etc., are archived for replay analysis.


