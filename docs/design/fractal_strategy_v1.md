# Design: Fractal Long/Short Strategy (v1)

## 1. Overview
The **Fractal Long/Short Strategy** leverages the platform's ability to compose independent "Sleeves" into a "Meta-Portfolio". Instead of forcing a single sleeve to manage both Long and Short positions internally, we decouple them into two atomic units:
1.  **Long Sleeve**: Captures upside momentum (MaxSharpe).
2.  **Short Sleeve**: Captures downside hedging (MinVariance/RiskParity).
3.  **Meta-Portfolio**: Optimizes the allocation (Hedge Ratio) between them.

## 2. Architecture

### 2.1 The Atomic Sleeves
Each sleeve acts as a specialized alpha factory.

| Property | Long Sleeve | Short Sleeve |
| :--- | :--- | :--- |
| **Profile** | `binance_spot_long_p10` | `binance_spot_short_p10` |
| **Logic** | Trend Following (Positive Momentum) | Mean Reversion / Trend (Negative Momentum) |
| **Ranking** | Descending (`Recommend.All` High -> Low) | Ascending (`Recommend.All` Low -> High) |
| **Filter** | Top 10 Percentile | Top 10 Percentile (of Ascending sort) |
| **Direction** | `LONG` | `SHORT` |
| **Solver** | `max_sharpe` (Aggressive) | `min_variance` (Conservative Hedge) |

### 2.2 The Meta-Portfolio
The Meta-Layer treats the sleeves as assets.

-   **Input**: Returns Stream of Long Sleeve + Returns Stream of Short Sleeve (Synthetic Long).
-   **Optimization**:
    -   Engine: `skfolio` / `custom`.
    -   Profile: `max_sharpe` or `risk_parity`.
    -   Constraint: `weights >= 0` (Since Short returns are already inverted).
-   **Result**: Dynamic allocation that shifts to Cash/Shorts during bear markets and leverages Longs during bull markets.

## 3. Implementation Details

### 3.1 Percentile Filtering (Pillar 1 Update)
We introduce a `PercentileFilter` to the HTR pipeline.
-   **Input**: Ranked list of candidates (sorted by score).
-   **Parameter**: `percentile` (float, e.g. 0.1).
-   **Logic**:
    ```python
    cutoff_index = int(len(ranked_candidates) * percentile)
    selected = ranked_candidates[:cutoff_index]
    vetoed = ranked_candidates[cutoff_index:]
    ```
-   **Application**: This ensures we only recruit the "cream of the crop" (or the "worst of the worst" for shorts) regardless of cluster structure.

### 3.2 Directional Integrity (Pillar 2)
-   **Long Sleeve**: Standard.
-   **Short Sleeve**:
    -   Scanner detects candidates.
    -   Feature Engineering computes scores (Low is good for shorting).
    -   `rankers` sorts Ascending (Low scores first).
    -   `PercentileFilter` picks top 10% (The lowest scores).
    -   `Policy` ensures `direction="SHORT"` is set.
    -   `Synthesis` inverts returns ($R_{syn} = -R_{raw}$).

### 3.3 Daily Rebalance (Pillar 3)
-   **Step Size**: `1` (Daily).
-   **Turnover Control**: The atomic solvers should use `turnover_penalty` to prevent excessive churn of the 10% boundary.

## 4. Workflow
1.  **DataOps**: Scan & Ingest `binance_spot` universe (Liquidity > $10M).
2.  **Alpha (Long)**: Run `binance_spot_long_p10`.
3.  **Alpha (Short)**: Run `binance_spot_short_p10`.
4.  **Meta**: Run `binance_spot_fractal_p10`.

## 5. Benefits
-   **Modularity**: Can tune Long and Short logic independently.
-   **Robustness**: Failure in one sleeve doesn't kill the portfolio (Meta-layer adapts).
-   **Explainability**: Easier to audit "Why did we go short?" (Because it was in the Short Sleeve) vs "Why did the single complex sleeve allocate negative weight?".
