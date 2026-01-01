# Specification: Universe Selection 3.0 (First Principles & Evolutionary Logic)

## 1. Foundational Axioms & Theoretical Grounding

1.  **Ergodicity & The Absorbing Barrier (Darwinian Survival)**: 
    - **Axiom**: Survival is the only prerequisite. 
    - **Evolutionary Analogy**: Selection precedes fitness. An organism that doesn't reach reproductive age has a fitness of zero.
    - **Source**: *Peters, O. (2019). "The ergodicity problem in economics." Nature Physics.*
    
2.  **Multiplicative Risk (Lethal Mutations)**:
    - **Axiom**: High performance cannot compensate for structural failure.
    - **Evolutionary Analogy**: Essential organs are a "Series System." Failure of the heart (Liquidity) cannot be offset by stronger legs (Alpha).
    - **Source**: *Taleb, N. N. (2012). "Antifragile."*

3.  **Information-Theoretic Connectivity (Niche Differentiation)**:
    - **Axiom**: Information overlap is the leading indicator of shared risk.
    - **Evolutionary Analogy**: Species in the same niche (shared risk drivers) compete for the same resources and are vulnerable to the same extinctions.
    - **Source**: *Gause, G. F. (1934). "The Struggle for Existence."*

## 2. Requirement: The Darwinian Health Gate (Extinction Testing)
- **Definition**: Assets must prove "Data Integrity" during specific **Stress Events**.
- **Theory**: **Regime Survival**. Only assets that have survived "Wild Randomness" windows (Mandelbrot) are eligible.
- **Source**: *Mandelbrot, B. B. (1997). "The Fractals of Financial Markets."*


## 3. Requirement: Multiplicative Probability Scoring (MPS)
- **Model**: $S_{total} = P_{health} \times P_{alpha} \times P_{liquidity}$
- **Logic**: Each component is normalized via CDF to a $[0, 1]$ probability. 
- **Goal**: Hard-veto of fragile assets.

## 5. Requirement: Downstream Engine Alignment (The Continuity Gate)

1.  **Numerical Stability (skfolio/cvxportfolio)**:
    - **Metric**: **Condition Number ($\kappa$)** of the return covariance matrix.
    - **Constraint**: $\kappa < 10^6$. If a selection creates a near-singular matrix (due to highly correlated duplicates), the selector must prune via **Hierarchical Recursive Bisection**.
    - **Theory**: Numerical conditioning ensures that optimizer weights are stable and not sensitive to minor price noise.

2.  **Transaction Cost Awareness (cvxportfolio)**:
    - **Metric**: **Estimated Cost of Implementation (ECI)**.
    - **Constraint**: $Gross\_Alpha - ECI > Threshold$.
    - **Logic**: Use the **Square-Root Impact Model**: $Cost \propto \sigma \sqrt{\frac{OrderSize}{ADV}}$.
    - **Source**: *Torre, N. (1997). "BARRA Market Impact Model."*

3.  **Metadata Completeness (Nautilus)**:
    - **Metric**: **Instrument Definition Parity**.
    - **Constraint**: All selected symbols must possess validated `tick_size`, `lot_size`, and `price_precision`. 
    - **Veto**: Any symbol lacking execution metadata is disqualified at the selection stage.


