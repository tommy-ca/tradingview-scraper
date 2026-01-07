# Specification: Universe Selection 3.0 (Darwinian Selection & MPS)

## 1. Foundational Axioms & Theoretical Grounding

1.  **Ergodicity & The Absorbing Barrier (Darwinian Survival)**: 
    - **Axiom**: Survival is the only prerequisite. 
    - **Evolutionary Analogy**: Selection precedes fitness. An organism that doesn't reach reproductive age has a fitness of zero.
    - **Implementation**: **Survival Veto Gate**. Assets with `P(Survival) < 0.1` are disqualified regardless of alpha.
    
2.  **Multiplicative Risk (Lethal Mutations)**:
    - **Axiom**: High performance cannot compensate for structural failure.
    - **Evolutionary Analogy**: Essential organs are a "Series System." Failure of the heart (Liquidity) cannot be offset by stronger legs (Alpha).
    - **Implementation**: **Log-Multiplicative Probability Scoring (LogMPS)**. Total score is the sum of log-probabilities: $S = \sum \omega_i \ln(P_i)$.

3.  **Information-Theoretic Connectivity (Niche Differentiation)**:
    - **Axiom**: Information overlap is the leading indicator of shared risk.
    - **Evolutionary Analogy**: Species in the same niche (shared risk drivers) compete for the same resources and are vulnerable to the same extinctions.
    - **Implementation**: **Cluster Battles**. Only the fittest asset survives per correlation cluster.

## 2. Requirement: The Darwinian Health Gate (Extinction Testing)
- **Definition**: Assets must prove "Data Integrity" during specific **Stress Events**.
- **Threshold**: `Regime_Survival_Score >= 0.1`.
- **Logic**: Absolute veto if missing history or failed stress test.

## 3. Requirement: Log-Multiplicative Probability Scoring (MPS 3.2)
- **Model**: $S_{total} = \exp(\sum \omega_i \ln(P_i))$
- **Components**:
    - **Momentum** ($P_{mom}$): Trend strength.
    - **Stability** ($P_{stab}$): Inverse volatility.
    - **Liquidity** ($P_{liq}$): Market depth.
    - **Antifragility** ($P_{af}$): Performance under stress.
    - **Predictability** ($P_{entropy}$, $P_{hurst}$): Spectral efficiency.
- **Goal**: Hard-veto of fragile or illiquid assets via near-zero multiplication (log-sum of negative infinity).

## 4. Requirement: Downstream Engine Alignment (The Continuity Gate)

1.  **Numerical Stability (Condition Number Gate)**:
    - **Metric**: **Condition Number ($\kappa$)** of the return covariance matrix.
    - **Constraint**: $\kappa < 10^6$. 
    - **Action**: If $\kappa \ge 10^6$, the system triggers **Aggressive Pruning**, restricting selection to exactly 1 winner per cluster to eliminate redundant highly-correlated assets.

2.  **Transaction Cost Awareness (Estimated Cost of Implementation - ECI)**:
    - **Logic**: Use the **Square-Root Impact Model**: $Cost = \sigma \sqrt{\frac{OrderSize}{ADV}}$.
    - **Constraint**: $Annualized\_Alpha - ECI > 0.02$ (2% net alpha floor).
    - **Veto**: Assets failing this net alpha test are disqualified (e.g., `UNG`, `USO`).

3.  **Metadata Completeness**:
    - **Metric**: **Instrument Definition Parity**.
    - **Requirement**: `tick_size`, `lot_size`, and `price_precision` must be present and valid. 
    - **Veto**: Any symbol lacking execution metadata is disqualified.

## 5. Modular Architecture (Selection Engines)

Selection logic is abstracted into versioned engines:
- **SelectionEngineV3_2 (MPS 3.2)**: High-stability Log-Probability standard (2026 Champion).
- **SelectionEngineV3.1 (MPS 3.1)**: Refined multiplicative standard.
- **SelectionEngineV2.1 (CARS 2.1)**: Champion additive standard (Global Multi-Norm).

## 6. Validation: Cluster Battles & "Liquid Winners"
The selection engine enforces "One Bet Per Factor" via **Cluster Battles**:
- **Mechanism**: Assets are grouped by Hierarchical Clustering (Ward Linkage).
- **Battle**: Assets within a cluster compete based on their LogMPS score.
- **Outcome**: The winner takes all allocation for that factor; losers are cut.
- **Example**: In the Silver Cluster (Run `20260107`), `AMEX:SLV` (Anchor, Score 0.0935) defeated `AMEX:AGQ` (2x Leveraged, Score 0.0264). The Stability component of the LogMPS score penalized the leveraged volatility, correctly prioritizing the core instrument for the selection phase. Leverage is reserved for the downstream Optimizer (Barbell Profile).

## 7. Profile Differentiation (Darwinian vs. Robust)

The V3 engine behavior is modulated by the selected profile:

### 7.1 Stability Gates ($\kappa$)
- **Darwinian Strictness**: Forces aggressive pruning (1 winner per cluster) at $\kappa \ge 10^6$.
- **Robust Strictness**: Extends the limit to $\kappa \ge 10^7$.

### 7.2 Execution Gates (ECI)
- **Darwinian ECI**: Strictly enforces the $Annualized\_Alpha - ECI > 0.02$ net floor.
- **Robust ECI**: Disables the hard ECI gate for experimental validation.

## 8. Audit & Feedback
- **Selection Alpha**: Measured by comparing the "Pruned" universe return vs the "Raw Pool" return.
- **Veto Trace**: Every disqualification is logged with a reason (e.g., "High Friction", "Low Survival") in `selection_audit.json`.
