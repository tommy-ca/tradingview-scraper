import argparse
import json
import logging
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

import numpy as np
import pandas as pd
from tqdm import tqdm

from tradingview_scraper.orchestration.registry import StageRegistry
from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.audit import get_df_hash
from tradingview_scraper.utils.technicals import TechnicalRatings
from tradingview_scraper.utils.predictability import (
    calculate_efficiency_ratio,
    calculate_hurst_exponent,
    calculate_permutation_entropy,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("backfill_features")


def _backfill_worker(symbol: str, lakehouse_dir: Path, metadata: Optional[Dict[str, Any]] = None) -> Optional[Dict[Tuple[str, str], pd.Series]]:
    """
    Worker function to calculate features for a single symbol.
    Runs in a separate process to leverage multi-core CPUs.
    """
    try:
        safe_sym = symbol.replace(":", "_")
        file_path = lakehouse_dir / f"{safe_sym}_1d.parquet"

        if not file_path.exists():
            return None

        df = pd.read_parquet(file_path)
        df.columns = [c.lower() for c in df.columns]

        # Ensure DatetimeIndex
        if "timestamp" in df.columns:
            df = df.set_index("timestamp")
        elif "date" in df.columns:
            df = df.set_index("date")

        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        if df.index.tz is not None:
            df.index = df.index.tz_convert(None)

        if "close" not in df.columns:
            return None

        df = df.sort_index()
        close = cast(pd.Series, df["close"])
        high = cast(pd.Series, df["high"])
        low = cast(pd.Series, df["low"])
        rets = close.pct_change()

        # 1. Statistical Features (Rolling - Phase 880)
        win = 252
        win_short = 120

        mom = rets.rolling(win).mean() * 252
        vol = rets.rolling(win).std() * np.sqrt(252)
        stability = 1.0 / (vol + 1e-9)

        efficiency = rets.rolling(win_short).apply(calculate_efficiency_ratio, raw=True)
        entropy = rets.rolling(win_short).apply(lambda x: calculate_permutation_entropy(x, order=5), raw=True)
        hurst = close.rolling(win_short).apply(calculate_hurst_exponent, raw=True)

        from scipy.stats import kurtosis, skew

        skewness = rets.rolling(win_short).apply(lambda x: float(abs(skew(x[~np.isnan(x)]))) if len(x[~np.isnan(x)]) > 2 else 0.0, raw=True)
        kurt = rets.rolling(win_short).apply(lambda x: float(kurtosis(x[~np.isnan(x)])) if len(x[~np.isnan(x)]) > 2 else 0.0, raw=True)
        cvar = rets.rolling(win_short).apply(lambda x: x[x <= np.nanquantile(x, 0.05)].mean() if len(x[~np.isnan(x)]) > 20 else -0.1, raw=True)

        # 2. Calculate Technicals using shared logic (Phase 630/640)
        ma = TechnicalRatings.calculate_recommend_ma_series(df)
        osc = TechnicalRatings.calculate_recommend_other_series(df)
        rating = TechnicalRatings.calculate_recommend_all_series(df)

        # 3. Expanded Technicals (CR-820)
        macd, macd_signal = TechnicalRatings.calculate_macd_series(close)
        mom_api = TechnicalRatings.calculate_mom_series(close)
        ao = TechnicalRatings.calculate_ao_series(high, low)
        stoch_k, stoch_d = TechnicalRatings.calculate_stoch_series(high, low, close)
        cci = TechnicalRatings.calculate_cci_series(high, low, close)
        willr = TechnicalRatings.calculate_willr_series(high, low, close)
        uo = TechnicalRatings.calculate_uo_series(high, low, close)
        bb_power = TechnicalRatings.calculate_bb_power_series(high, low, close)
        ichimoku_kijun = TechnicalRatings.calculate_ichimoku_kijun_series(high, low, close)

        # 4. Trend Indicators (Phase 1110)
        # Used for TrendRegimeFilter (SMA200, VWMA20)
        sma_50 = close.rolling(window=50).mean()
        sma_200 = close.rolling(window=200).mean()

        # VWMA 20: Volume Weighted Moving Average
        # Formula: sum(Close * Volume, N) / sum(Volume, N)
        pv = close * df["volume"]
        vwma_20 = pv.rolling(window=20).sum() / df["volume"].rolling(window=20).sum()

        # 6. Advanced Trend Indicators (Phase 1210)
        # ADX/DMI
        adx, dmp, dmn = TechnicalRatings.calculate_adx_full_series(high, low, close)
        # Donchian
        dc_l, dc_m, dc_u = TechnicalRatings.calculate_donchian_series(high, low, length=20)
        # BB Width
        bb_width = TechnicalRatings.calculate_bb_width_series(close, length=20, std=2.0)

        # 7. Metadata Override (Phase 890)
        if metadata:
            mapping = {
                "Recommend.All": "recommend_all",
                "Recommend.MA": "recommend_ma",
                "Recommend.Other": "recommend_other",
                "ADX": "adx",
                "RSI": "rsi",
                "Mom": "mom",
                "AO": "ao",
                "CCI20": "cci",
                "W.R": "willr",
                "UO": "uo",
                "BBPower": "bb_power",
                "Ichimoku.BLine": "ichimoku_kijun",
            }
            for tv_key, int_key in mapping.items():
                val = metadata.get(tv_key)
                if val is not None and not np.isnan(val):
                    if int_key == "recommend_all":
                        rating.iloc[-1] = float(val)
                    elif int_key == "recommend_ma":
                        ma.iloc[-1] = float(val)
                    elif int_key == "recommend_other":
                        osc.iloc[-1] = float(val)
                    elif int_key == "mom":
                        mom_api.iloc[-1] = float(val)
                    elif int_key == "ao":
                        ao.iloc[-1] = float(val)
                    elif int_key == "cci":
                        cci.iloc[-1] = float(val)
                    elif int_key == "willr":
                        willr.iloc[-1] = float(val)
                    elif int_key == "uo":
                        uo.iloc[-1] = float(val)
                    elif int_key == "bb_power":
                        bb_power.iloc[-1] = float(val)
                    elif int_key == "ichimoku_kijun":
                        ichimoku_kijun.iloc[-1] = float(val)

        ma = ma.ffill(limit=3)
        osc = osc.ffill(limit=3)
        rating = rating.ffill(limit=3)

        return {
            (symbol, "momentum"): mom,
            (symbol, "stability"): stability,
            (symbol, "entropy"): entropy.fillna(1.0).clip(0, 1),
            (symbol, "efficiency"): efficiency,
            (symbol, "hurst_clean"): (1.0 - (hurst.fillna(0.5) - 0.5).abs() * 2.0).clip(0, 1),
            (symbol, "skew"): skewness,
            (symbol, "kurtosis"): kurt,
            (symbol, "cvar"): cvar,
            (symbol, "recommend_ma"): ma,
            (symbol, "recommend_other"): osc,
            (symbol, "recommend_all"): rating,
            (symbol, "macd"): macd,
            (symbol, "macd_signal"): macd_signal,
            (symbol, "mom"): mom_api,
            (symbol, "ao"): ao,
            (symbol, "stoch_k"): stoch_k,
            (symbol, "stoch_d"): stoch_d,
            (symbol, "cci"): cci,
            (symbol, "willr"): willr,
            (symbol, "uo"): uo,
            (symbol, "bb_power"): bb_power,
            (symbol, "ichimoku_kijun"): ichimoku_kijun,
            (symbol, "sma_50"): sma_50,
            (symbol, "sma_200"): sma_200,
            (symbol, "vwma_20"): vwma_20,
            (symbol, "adx_14"): adx,
            (symbol, "dmp_14"): dmp,
            (symbol, "dmn_14"): dmn,
            (symbol, "donchian_lower_20"): dc_l,
            (symbol, "donchian_upper_20"): dc_u,
            (symbol, "bb_width_20"): bb_width,
        }
    except Exception:
        return None


class BackfillService:
    def __init__(self, lakehouse_dir: Optional[Path] = None):
        settings = get_settings()
        self.lakehouse_dir = lakehouse_dir or settings.lakehouse_dir

    def _get_lakehouse_symbols(self) -> List[str]:
        symbols = []
        for p in self.lakehouse_dir.glob("*_1d.parquet"):
            stem = p.stem.replace("_1d", "")
            if "_" in stem:
                parts = stem.split("_", 1)
                symbols.append(f"{parts[0]}:{parts[1]}")
        return sorted(symbols)

    def run(self, candidates_path: Optional[Path] = None, output_path: Optional[Path] = None, strict_scope: bool = True):
        settings = get_settings()
        out_p = output_path or (settings.lakehouse_dir / "features_matrix.parquet")

        if not candidates_path or not candidates_path.exists():
            if strict_scope:
                raise ValueError("Candidates file is REQUIRED for backfilling (Global backfill is forbidden).")
            logger.warning("No candidates file provided. Scanning full Lakehouse.")
            symbols = self._get_lakehouse_symbols()
            symbol_metadata = {}
        else:
            with open(candidates_path, "r") as f:
                candidates = json.load(f)
            symbol_metadata = {(c.get("physical_symbol") or c.get("symbol")): c for c in candidates}
            symbols = sorted(list(symbol_metadata.keys()))

            if not symbols and strict_scope:
                logger.error(f"❌ Scoped backfill requested but candidates file {candidates_path} is empty.")
                raise ValueError("Candidates list is empty. Scoped backfill cannot proceed.")

            logger.info(f"Scoped backfill: {len(symbols)} symbols from {candidates_path}")

        symbols = [s for s in symbols if (self.lakehouse_dir / f"{s.replace(':', '_')}_1d.parquet").exists()]
        logger.info(f"Processing {len(symbols)} symbols...")

        existing_df = pd.DataFrame()
        if out_p.exists():
            try:
                existing_df = pd.read_parquet(out_p)
                logger.info(f"Loaded existing matrix: {existing_df.shape}")
            except Exception as e:
                logger.warning(f"Failed to load existing: {e}")

        all_features = {}
        max_workers = os.cpu_count() or 4
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_backfill_worker, sym, self.lakehouse_dir, symbol_metadata.get(sym)): sym for sym in symbols}
            for future in tqdm(as_completed(futures), total=len(futures), desc="Backfilling"):
                symbol = futures[future]
                try:
                    res = future.result()
                    if res:
                        all_features.update(res)
                except Exception as e:
                    logger.error(f"Worker failed for {symbol}: {e}")

        if not all_features and existing_df.empty:
            logger.error("No data produced.")
            return

        new_df = pd.DataFrame(all_features)
        if not new_df.empty:
            new_df.columns.names = ["symbol", "feature"]
            new_df = new_df.dropna(how="all")

        if not existing_df.empty:
            if not new_df.empty:
                combined_idx = existing_df.index.union(new_df.index).sort_values()
                existing_aligned = existing_df.reindex(combined_idx)
                new_aligned = new_df.reindex(combined_idx)

                # Single block assignment to avoid fragmented frame warnings
                final_df = existing_aligned.copy()
                final_df[new_aligned.columns] = new_aligned
            else:
                final_df = existing_df
        else:
            final_df = new_df

        if final_df.empty:
            logger.error("Final matrix empty.")
            return

        from tradingview_scraper.utils.features import FeatureConsistencyValidator
        from tradingview_scraper.pipelines.selection.base import FoundationHealthRegistry

        registry = FoundationHealthRegistry(path=self.lakehouse_dir / "foundation_health.json")
        report = FeatureConsistencyValidator.validate_history(final_df, strict=(os.getenv("TV_STRICT_HEALTH") == "1"))

        # Registry updates
        for sym in report.get("degraded", []):
            registry.update_status(sym, "toxic", reason="feature_nan_density")
        for sym in report.get("lagging", []):
            registry.update_status(sym, "stale", reason="feature_lag")
        registry.save()

        if os.getenv("TV_STRICT_HEALTH") == "1" and (report["degraded"] or report["lagging"]):
            raise RuntimeError(f"Audit Failed: {report}")

        out_p.parent.mkdir(parents=True, exist_ok=True)
        temp_p = out_p.with_suffix(".tmp")
        final_df.to_parquet(temp_p)
        temp_p.replace(out_p)
        logger.info(f"Saved {out_p} | Shape: {final_df.shape}")


@StageRegistry.register(id="foundation.backfill", name="Feature Backfill", description="Generates PIT features matrix", category="foundation")
def backfill_features_stage(candidates_path: Optional[str] = None, output_path: Optional[str] = None, lakehouse_dir: Optional[str] = None, strict_scope: bool = True):
    service = BackfillService(lakehouse_dir=Path(lakehouse_dir) if lakehouse_dir else None)
    service.run(candidates_path=Path(candidates_path) if candidates_path else None, output_path=Path(output_path) if output_path else None, strict_scope=strict_scope)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", help="Path to candidates.json")
    parser.add_argument("--output", help="Output path")
    parser.add_argument("--lakehouse", help="Lakehouse path")
    parser.add_argument("--strict-scope", action="store_true", default=True)
    parser.add_argument("--no-strict", action="store_false", dest="strict_scope")
    args = parser.parse_args()
    BackfillService(lakehouse_dir=Path(args.lakehouse) if args.lakehouse else None).run(
        candidates_path=Path(args.candidates) if args.candidates else None, output_path=Path(args.output) if args.output else None, strict_scope=args.strict_scope
    )
