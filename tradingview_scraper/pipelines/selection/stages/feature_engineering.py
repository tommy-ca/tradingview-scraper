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

        # 1. Resolve PIT Features (Phase 810)
        # Passed from BacktestEngine for rebalance-time fidelity
        pit_features = context.params.get("pit_features")

        # 2. Resolve Discovery Metadata (Live Discovery)
        candidate_map = {c["symbol"]: c for c in context.raw_pool}

        # 3. Resolve Offline Store (Lakehouse)
        settings = get_settings()
        master_path = settings.lakehouse_dir / "features_matrix.parquet"

        # 4. Helper: Extract feature value from available sources
        def get_feature_value(sym: str, feature: str) -> float:
            # Source 1: PIT Injection (Backtest rebalance date)
            if pit_features is not None:
                try:
                    val = pit_features.get((sym, feature))
                    if val is not None and not pd.isna(val):
                        return float(val)
                except Exception:
                    pass

            # Source 2: Discovery Metadata (Fresh TV Rating)
            # Map common technicals
            tv_map = {
                "recommend_all": "Recommend.All",
                "recommend_ma": "Recommend.MA",
                "recommend_other": "Recommend.Other",
                "adx": "ADX",
                "rsi": "RSI",
                "macd": "MACD.macd",
                "ichimoku_kijun": "Ichimoku.BLine",
            }
            meta = candidate_map.get(sym, {})
            val = meta.get(tv_map.get(feature, feature)) or meta.get(feature)
            if val is not None and not pd.isna(val):
                return float(val)

            return np.nan

        # 5. Build Feature Matrix for current universe
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

        logger.info(f"Loading features for {len(df.columns)} assets (Offline-Only Standard)...")

        # We attempt to populate from sources
        feature_data = {}
        for feat in all_feature_names:
            feature_data[feat] = pd.Series({s: get_feature_value(s, feat) for s in df.columns})

        features = pd.DataFrame(feature_data)

        # 6. Critical Fallback: Load from Master Matrix if still missing important features
        # (Only if we are not in a strict backtest where PIT injection is mandatory)
        if features.isna().all().all() and pit_features is None:
            if master_path.exists():
                try:
                    master_df = pd.read_parquet(master_path)
                    # Extract last available values for current universe
                    for s in df.columns:
                        if s in master_df.columns.get_level_values(0):
                            for f in all_feature_names:
                                if pd.isna(features.loc[s, f]):
                                    try:
                                        features.loc[s, f] = float(master_df[(s, f)].iloc[-1])
                                    except Exception:
                                        pass
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
