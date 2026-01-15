# Strategy Integration Requirements v1 (Modular Design)

## 1. Overview
The platform is transitioning to a modular strategy architecture where alpha sources (Atoms) are grouped into **Strategies** within the manifest and integrated into the global v4 Selection & Allocation pipeline.

## 2. Manifest Abstraction (Strategies vs Pipelines)
To ensure precise logic assignment and organizational clarity, the `discovery` block in `manifest.json` now supports a `strategies` layer.

### 2.1 Schema Definition
- **Profile**: Contains a `discovery` block.
- **Strategy**: A named group of scanners (e.g., `rating_ma`, `vol_breakout`).
- **Logic Injection**: The name of the strategy is automatically injected as the `logic` field for all atoms discovered by its scanners.

Example Manifest:
```json
"discovery": {
  "strategies": {
    "rating_ma": {
      "scanners": ["scanners/crypto/ratings/binance_perp_rating_ma_long", ...],
      "interval": "1d"
    }
  }
}
```

## 3. The Strategy Atom
Each Atom is defined by a triplet: `(Asset, Logic, Direction)`.
- **Asset**: Canonical symbol (e.g., `BINANCE:BTCUSDT`).
- **Logic**: The alpha generation strategy name (e.g., `rating_all`, `rating_ma`, `rating_osc`).
- **Direction**: `LONG` or `SHORT`.

## 4. Modular Scanners (Trend Following)
Scanners must emit candidates with enriched technical ratings from TradingView.

### 4.1 technical_rating_scanner
- **Source**: TradingView `Recommend.All`, `Recommend.MA`, `Recommend.Other`.
- **Ranking Logic**:
    - **LONG**: `Recommend.* > 0.0` (Strict Buy/Strong Buy only).
    - **SHORT**: `Recommend.* < 0.0` (Strict Sell/Strong Sell only).
- **Institutional Liquidity Floors**:
    - **Perpetuals**: `Value.Traded > 50,000,000 USD`.
    - **Spot**: `Value.Traded > 20,000,000 USD`.
- **Base Universe Standard (L1)**:
    - Discovery scanners must inherit from the audited pure baseline configurations to ensure strict venue isolation:
        - `binance_spot_base.yaml`: Enforces strictly **>$20M 24h Volume** and `type: spot`.
        - `binance_perp_base.yaml`: Enforces strictly **>$50M 24h Volume** and `type: swap`.
    - **Venue Isolation**: Spot and Perp outputs are strictly separated. Scanners must not mix assets from different market types to maintain implementation purity.
    - **Purity Standard**: Base scanners utilize explicit TradingView server-side filters (`filters` list) and avoid redundant Pydantic-side `volume` blocks.
    - **Zero Alpha Bias**: Base pools are unranked (sorted by `name`) and stripped of all technical gates to ensure 100% data density for downstream Inference.
- **Discovery Sorting**: 
    - Scanners must sort by the primary rating (e.g. `Recommend.All`, `Recommend.MA`) during discovery to ensure the most extreme sentiment signals are recruited first.
    - **LONG**: `sort_by: RatingField, order: desc`.
    - **SHORT**: `sort_by: RatingField, order: asc`.
- **Output**: A candidates manifest containing ratings and intended direction.
- **Target Recruitment Pool**:
    - The discovery suite targets a total "Raw Pool" of ~100-150 unique candidates.
    - Scanners are configured with a limit of **100 items per strategy** to ensure sufficient depth for the HTR relaxation loop.


## 5. Tier 2 Alpha Features (Enrichment)
To enable advanced scoring and risk partitioning in the Selection Pipeline, the following fields are persisted but not used for discovery-stage filtering.

### 5.1 volatility_d (Volatility.D)
- **Source**: TradingView daily trailing volatility.
- **Usage**: Used in `PartitioningStage` to prevent high-volatility atoms from dominating risk-parity clusters.

### 5.2 volume_change_pct (volume_change)
- **Source**: TradingView 24h volume change percentage.
- **Usage**: Used in `InferenceStage` as a "Momentum Confirmation" multiplier; positive volume spikes confirm the conviction of rating signals.

### 5.3 rate_of_change (ROC)
- **Source**: TradingView Rate of Change indicator.
- **Usage**: Used in `InferenceStage` as a core momentum feature to capture the velocity of price movement over the standard lookback period.

## 6. Pipeline Integration

### 6.1 Data Persistence
Technical ratings must be preserved from the **Discovery** stage through the **Lakehouse** and into the **Inference** stage.
- **Lakehouse Metadata**: `portfolio_meta.json` must store ratings as features.
- **Deduplication**: Atoms with the same `(Asset, Logic)` must be pruned based on rating strength or liquidity.
- **Venue Isolation**: Spot and Perpetual outputs are strictly separated at the discovery stage. Scanners are partitioned by market type (`type: spot` vs `type: swap`) to prevent cross-venue implementation errors.
- **Workflow Isolation**: Rating-based strategies are managed via the `crypto_rating_alpha` profile to prevent dilution of standard trend-following sleeves.

### 6.2 Selection Pipeline (v4)
- **Feature Engineering**: Ratings should be used as primary alpha scores or as confirmation filters.
- **Clustering (HRP)**: Assets discovered via different logic modules should be clustered together to ensure portfolio-wide factor diversity.

## 7. Implementation Roadmap
1. **Audit & Patch Ingestion**: Ensure `Recommend.MA` and `Recommend.Other` are captured by `FuturesUniverseSelector`.
2. **Consolidator Update**: Update `select_top_universe.py` to map ratings to candidates.
3. **Feature Storage**: Update `prepare_portfolio_data.py` to store ratings in `portfolio_meta.json`.
4. **Scanner Development**: Build a dedicated trend rating scanner config and validation script.
