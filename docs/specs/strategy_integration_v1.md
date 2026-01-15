# Strategy Integration Requirements v1 (Modular Design)

## 1. Overview
The platform is transitioning to a modular strategy architecture where alpha sources (Atoms) can be discovered via specialized scanners and integrated into the global v4 Selection & Allocation pipeline.

## 2. The Strategy Atom
Each Atom is defined by a triplet: `(Asset, Logic, Direction)`.
- **Asset**: Canonical symbol (e.g., `BINANCE:BTCUSDT`).
- **Logic**: The alpha generation engine (e.g., `trend_following`, `mean_reversion`, `rating_trend`).
- **Direction**: `LONG` or `SHORT`.

## 3. Modular Scanners (Trend Following)
Scanners must emit candidates with enriched technical ratings from TradingView.

### 3.1 technical_rating_scanner
- **Source**: TradingView `Recommend.All`, `Recommend.MA`, `Recommend.Other`.
- **Ranking Logic**:
    - **LONG**: `Recommend.All > 0.5` AND `Recommend.MA > 0.5`.
    - **SHORT**: `Recommend.All < -0.5` AND `Recommend.MA < -0.5`.
- **Institutional Liquidity Floors**:
    - **Perpetuals**: `Value.Traded > 50M USD`.
    - **Spot**: `Value.Traded > 20M USD`.
- **Discovery Sorting**: 
    - Scanners must sort by `Recommend.All` during discovery to ensure the most extreme sentiment signals are recruited first.
    - **LONG**: `sort_by: Recommend.All, order: desc`.
    - **SHORT**: `sort_by: Recommend.All, order: asc`.
- **Output**: A candidates manifest containing ratings and intended direction.

## 4. Pipeline Integration
### 4.1 Data Persistence
Technical ratings must be preserved from the **Discovery** stage through the **Lakehouse** and into the **Inference** stage.
- **Lakehouse Metadata**: `portfolio_meta.json` must store ratings as features.
- **Deduplication**: Atoms with the same `(Asset, Logic)` must be pruned based on rating strength or liquidity.
- **Workflow Isolation**: Rating-based strategies are managed via the `crypto_rating_alpha` profile to prevent dilution of standard trend-following sleeves.

### 4.2 Selection Pipeline (v4)
- **Feature Engineering**: Ratings should be used as primary alpha scores or as confirmation filters.
- **Clustering (HRP)**: Assets discovered via different logic modules should be clustered together to ensure portfolio-wide factor diversity.

## 5. Implementation Roadmap
1. **Audit & Patch Ingestion**: Ensure `Recommend.MA` and `Recommend.Other` are captured by `FuturesUniverseSelector`.
2. **Consolidator Update**: Update `select_top_universe.py` to map ratings to candidates.
3. **Feature Storage**: Update `prepare_portfolio_data.py` to store ratings in `portfolio_meta.json`.
4. **Scanner Development**: Build a dedicated trend rating scanner config and validation script.
