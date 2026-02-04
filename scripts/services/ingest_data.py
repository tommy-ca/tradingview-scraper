import json
import logging
import os
import time
from pathlib import Path
from typing import Any, cast

import pandas as pd

from tradingview_scraper.pipelines.selection.base import (
    AdvancedToxicityValidator,
    FoundationHealthRegistry,
)
from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.security import SecurityUtils

# Assume PersistentDataLoader is available via PYTHONPATH or install
try:
    from tradingview_scraper.symbols.stream.persistent_loader import PersistentDataLoader
except ImportError:
    # For testing environment where package might not be installed
    PersistentDataLoader = None  # type: ignore

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ingestion_service")


def _is_fresh(symbol: str, lakehouse_dir: Path, freshness_hours: int) -> bool:
    """Check if symbol data exists and is fresh."""
    try:
        p_path = SecurityUtils.get_safe_path(lakehouse_dir, symbol)
    except ValueError as e:
        logger.error(f"Security/Validation error for {symbol}: {e}")
        return False

    if not p_path.exists():
        return False

    mtime = p_path.stat().st_mtime
    age_hours = (time.time() - mtime) / 3600

    if age_hours < freshness_hours:
        logger.debug(f"{symbol} is fresh ({age_hours:.1f}h < {freshness_hours}h). Skipping.")
        return True

    logger.info(f"{symbol} is stale ({age_hours:.1f}h). Queueing for fetch.")
    return False


def _is_toxic(df: pd.DataFrame) -> bool:
    """Check for >500% daily returns."""
    if "close" not in df.columns:
        return False

    # Calculate returns
    # Sort by timestamp just in case
    if "timestamp" in df.columns:
        df = df.sort_values("timestamp")

    pct = df["close"].pct_change().dropna()
    if pct.empty:
        return False

    if pct.max() > 5.0:  # 500%
        return True
    if pct.min() < -0.99:  # -99% drop (suspicious for some assets, but maybe real. Keep focus on upside spikes)
        # Actually -99% happens in crypto rugs. The spike is the main "contamination" issue.
        pass

    return False


def ingest_candidates_list(
    candidates: list[dict[str, Any]],
    lakehouse_dir: Path | None = None,
    freshness_hours: int = 12,
    lookback_days: int = 500,
):
    """
    Main ingestion logic:
    1. Filter candidates for freshness (Idempotency).
    2. Fetch missing/stale data.
    3. Validate toxicity.
    4. Commit to Lakehouse (PersistentLoader does this, but we validate before).
    """
    settings = get_settings()
    lh_dir = lakehouse_dir or settings.lakehouse_dir

    # Ensure lakehouse exists
    lh_dir.mkdir(parents=True, exist_ok=True)

    # Initialize dependencies
    loader = PersistentDataLoader(lakehouse_path=str(lh_dir)) if PersistentDataLoader else None
    registry = FoundationHealthRegistry(path=lh_dir / "foundation_health.json")

    if not loader:
        raise RuntimeError("PersistentDataLoader not initialized.")

    # 1. Filter
    # Validate that 'c' is a dictionary and has 'symbol'
    validated_candidates = []
    for c in candidates:
        if isinstance(c, dict) and "symbol" in c:
            try:
                # Validate symbol before adding to fetch list
                SecurityUtils.get_safe_path(lh_dir, c["symbol"])
                validated_candidates.append(c)
            except ValueError as e:
                logger.error(f"Validation failed for {c['symbol']}: {e}")
        else:
            logger.warning(f"Skipping invalid candidate format: {c}")

    to_fetch = [c for c in validated_candidates if not _is_fresh(c["symbol"], lh_dir, freshness_hours)]

    if not to_fetch:
        logger.info("All candidates are fresh. No ingestion needed.")
        return

    logger.info(f"Ingesting {len(to_fetch)} symbols...")

    # 2. Fetch Loop (Sequential for safety, or threaded in real prod)
    for item in to_fetch:
        symbol = item["symbol"]
        try:
            # Use sync to fetch data. The loader handles writing to parquet usually,
            # but we want to intercept for toxic check if possible.
            # However, PersistentLoader writes directly.
            # To implement "Toxic Filter AT SOURCE", we rely on the fact that
            # loader.load() reads what was just synced.

            # Fetch
            # Depth should cover lookback + buffer
            depth = lookback_days + 100
            loader.sync(symbol, interval="1d", depth=depth, total_timeout=300)

            # 3. Post-Fetch Validation (Toxic Check)
            # We load what was just written to check integrity
            # Note: PersistentLoader writes to 'data/lakehouse' by default in the project config.
            # If we injected a custom lakehouse_dir, we hope PersistentLoader respects it or we verify the real path.
            # For this implementation, we assume PersistentLoader writes to lh_dir or standard location.

            # Verify Toxic
            # We use the loader to load back the dataframe
            # Note: 'load' might return cached data if we don't force reload?
            # Usually it reads from disk.

            # Let's assume standard path for validation
            p_path = SecurityUtils.get_safe_path(lh_dir, symbol)

            if p_path.exists():
                df = pd.read_parquet(p_path)

                is_toxic_ret = _is_toxic(df)
                is_toxic_vol = AdvancedToxicityValidator.is_volume_toxic(cast(pd.Series, df["volume"])) if "volume" in df.columns else False
                is_stalled = AdvancedToxicityValidator.is_price_stalled(cast(pd.Series, df["close"])) if "close" in df.columns else False

                if is_toxic_ret or is_toxic_vol or is_stalled:
                    reason = "return_spike" if is_toxic_ret else ("volume_spike" if is_toxic_vol else "price_stall")
                    logger.warning(f"TOXIC DATA DETECTED for {symbol} (Reason: {reason}). Deleting corrupted file.")
                    os.remove(p_path)
                    registry.update_status(symbol, status="toxic", reason=reason)
                else:
                    logger.info(f"Successfully ingested {symbol}")
                    registry.update_status(symbol, status="healthy")

                registry.save()

        except Exception as e:
            logger.error(f"Failed to ingest {symbol}: {e}")


def ingest_candidates_from_file(
    file_path: Path,
    lakehouse_dir: Path | None = None,
    freshness_hours: int = 12,
):
    """Load candidates from JSON and ingest."""
    if not file_path.exists():
        logger.error(f"Candidate file not found: {file_path}")
        return

    with open(file_path, "r") as f:
        data = json.load(f)

    # Handle {meta, data} envelope or raw list
    candidates = []
    if isinstance(data, dict):
        if "data" in data and isinstance(data["data"], list):
            candidates = data["data"]
        else:
            logger.error(f"Invalid JSON envelope in {file_path}. Expected 'data' list.")
            return
    elif isinstance(data, list):
        candidates = data
    else:
        logger.error(f"Unknown JSON format in {file_path}")
        return

    ingest_candidates_list(
        candidates,
        lakehouse_dir=lakehouse_dir,
        freshness_hours=freshness_hours,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", help="Path to candidates.json", required=True)
    parser.add_argument("--lakehouse", help="Path to lakehouse dir", default=None)
    args = parser.parse_args()

    lakehouse_arg = Path(args.lakehouse) if args.lakehouse else None

    # We now call the function directly
    ingest_candidates_from_file(Path(args.candidates), lakehouse_dir=lakehouse_arg)
