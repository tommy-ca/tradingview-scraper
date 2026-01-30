import logging

import numpy as np
import pandas as pd

from tradingview_scraper.orchestration.registry import StageRegistry
from tradingview_scraper.pipelines.selection.base import BasePipelineStage, SelectionContext
from tradingview_scraper.settings import get_settings

logger = logging.getLogger("pipelines.selection.feature_engineering")


@StageRegistry.register(id="foundation.features", name="Feature Engineering", description="Calculates technical alpha factors", category="foundation")
class FeatureEngineeringStage(BasePipelineStage):
    """
    Stage 2: Feature Generation (Offline Standard).
    Loads technical and statistical alpha factors from the PIT Feature Store or Discovery Metadata.
    """

    @property
    def name(self) -> str:
        return "FeatureEngineering"

    def execute(self, context: SelectionContext) -> SelectionContext:
        df = context.returns_df
        if df.empty:
            logger.warning("FeatureEngineeringStage: Returns matrix is empty. Skipping.")
            return context

        # 1. Setup Feature Definitions
        all_feature_names = [
            "momentum",
            "stability",
            "entropy",
            "efficiency",
            "hurst_clean",
            "skew",
            "kurtosis",
            "cvar",
            "adx",
            "rsi",
            "recommend_all",
            "recommend_ma",
            "recommend_other",
            "roc",
            "macd",
            "macd_signal",
            "mom",
            "ao",
            "stoch_k",
            "stoch_d",
            "cci",
            "willr",
            "uo",
            "bb_power",
            "ichimoku_kijun",
        ]

        # 2. Vectorized Construction: Metadata Source (Live Discovery)
        # Start with Metadata as base
        meta_features = pd.DataFrame(np.nan, index=df.columns, columns=pd.Index(all_feature_names))

        if context.raw_pool:
            pool_df = pd.DataFrame(context.raw_pool)
            if not pool_df.empty and "symbol" in pool_df.columns:
                pool_df = pool_df.set_index("symbol")
                # Filter to current universe
                pool_df = pool_df.reindex(df.columns)

                tv_map = {
                    "recommend_all": "Recommend.All",
                    "recommend_ma": "Recommend.MA",
                    "recommend_other": "Recommend.Other",
                    "adx": "ADX",
                    "rsi": "RSI",
                    "macd": "MACD.macd",
                    "ichimoku_kijun": "Ichimoku.BLine",
                }

                # Batch assignment
                for feat in all_feature_names:
                    source_col = tv_map.get(feat, feat)
                    if source_col in pool_df.columns:
                        meta_features[feat] = pd.to_numeric(pool_df[source_col], errors="coerce")

        features = meta_features

        # 3. Vectorized Construction: PIT Source (Point-in-Time Injection)
        # PIT takes precedence over Metadata
        pit_features = context.params.get("pit_features")
        if pit_features:
            try:
                # pit_features is {(sym, feat): val}
                idx = pd.MultiIndex.from_tuples(pit_features.keys(), names=["symbol", "feature"])
                pit_s = pd.Series(list(pit_features.values()), index=idx)
                # Unstack to (symbol, feature)
                pit_df = pit_s.unstack(level="feature")
                # Align to current universe
                pit_df = pit_df.reindex(index=df.columns, columns=all_feature_names)
                # Combine: values in pit_df overwrite anything else, but combine_first fills nulls in self with other
                # So we use pit_df.combine_first(features) to prioritize PIT
                features = pit_df.combine_first(features)
            except Exception as e:
                logger.warning(f"Vectorized PIT injection failed: {e}")

        logger.info(f"Loading features for {len(df.columns)} assets (Vectorized Standard)...")

        # 4. Critical Fallback: Master Matrix (Lakehouse)
        # Only if we are fully empty (meaning no live metadata and no PIT)
        if features.isna().all().all() and pit_features is None:
            settings = get_settings()
            master_path = settings.lakehouse_dir / "features_matrix.parquet"
            if master_path.exists():
                try:
                    master_df = pd.read_parquet(master_path)
                    # Master DF has MultiIndex columns (Symbol, Feature)
                    # We want the last row
                    if not master_df.empty:
                        last_vals = master_df.iloc[-1]
                        # Unstack to get Symbol x Feature
                        master_latest = last_vals.unstack(level=1)
                        # Align and merge
                        master_latest = master_latest.reindex(index=df.columns, columns=all_feature_names)
                        features = features.combine_first(master_latest)
                        logger.info("Enriched features from Master Lakehouse Matrix.")
                except Exception as e:
                    logger.warning(f"Failed to load master features: {e}")

        # 7. Final Sanity / Defaulting
        # We fill NaNs with safe defaults to prevent solver crashes
        if "entropy" in features.columns:
            features["entropy"] = features["entropy"].fillna(1.0)
        if "hurst_clean" in features.columns:
            features["hurst_clean"] = features["hurst_clean"].fillna(0.5)

        features = features.fillna(0.0).astype(float)

        # 8. Data Source Attribution
        source_label = "PIT_INJECTION" if pit_features is not None else "METADATA_OR_STORE"
        logger.info(f"Feature Engineering Stage: Source={source_label}")

        # 9. L1 Data Contract Validation

        from tradingview_scraper.pipelines.contracts import FeatureStoreSchema

        try:
            FeatureStoreSchema.validate(features)
        except Exception as e:
            logger.error(f"L1 Data Contract Violation in feature_store: {e}")
            raise

        context.feature_store = features
        context.log_event(self.name, "FeaturesLoaded", {"n_features": len(features.columns), "n_assets": len(features)})

        return context
