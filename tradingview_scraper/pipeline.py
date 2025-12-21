import asyncio
import logging
from typing import Dict, List, Optional

from tradingview_scraper.futures_universe_selector import FuturesUniverseSelector, load_config
from tradingview_scraper.symbols.screener_async import AsyncScreener
from tradingview_scraper.symbols.stream.metadata import MetadataCatalog

logger = logging.getLogger(__name__)


class QuantitativePipeline:
    """
    Unified orchestrator for the full end-to-end quantitative workflow.
    Discovery -> Alpha -> Risk -> Catalog
    """

    def __init__(self, lakehouse_path: str = "data/lakehouse"):
        self.lakehouse_path = lakehouse_path
        self.catalog = MetadataCatalog(base_path=lakehouse_path)
        self.screener = AsyncScreener()

    async def run_discovery_async(self, config_paths: List[str], limit: Optional[int] = None) -> List[Dict]:
        """
        Stage 1 & 2: Discover high-liquidity symbols and apply strategy filters in parallel.
        """
        selectors = {}
        all_payloads = []
        payload_map = []  # To map raw results back to configs

        for path in config_paths:
            try:
                cfg = load_config(path)
                if limit:
                    cfg.limit = limit
                    cfg.base_universe_limit = limit

                selector = FuturesUniverseSelector(cfg)
                # Use dry_run to extract payloads
                dry_res = selector.run(dry_run=True)
                payloads = dry_res.get("payloads", [])

                for p in payloads:
                    all_payloads.append(p)
                    payload_map.append(path)

                selectors[path] = selector
            except Exception as e:
                logger.error(f"Failed to initialize selector for {path}: {e}")

        if not all_payloads:
            return []

        # Execute all screens in parallel
        logger.info(f"Executing {len(all_payloads)} parallel screens across {len(config_paths)} configs...")
        raw_results = await self.screener.screen_many(all_payloads)

        # Aggregate raw data by config path
        aggregated_raw = {path: [] for path in config_paths}
        for i, res in enumerate(raw_results):
            path = payload_map[i]
            if res["status"] == "success":
                aggregated_raw[path].extend(res["data"])
            else:
                logger.warning(f"Screen failed for payload {i} ({path}): {res.get('error')}")

        # Post-process via selectors
        all_signals = []
        for path, raw_data in aggregated_raw.items():
            if not raw_data:
                continue

            try:
                selector = selectors[path]
                processed = selector.process_data(raw_data)
                signals = processed.get("data", [])

                direction = "LONG" if "short" not in path.lower() else "SHORT"
                for s in signals:
                    s["direction"] = direction

                all_signals.extend(signals)
                logger.info(f"  Generated {len(signals)} signals from {path}.")
            except Exception as e:
                logger.error(f"Post-processing failed for {path}: {e}")

        return all_signals

    def run_discovery(self, config_paths: List[str], limit: Optional[int] = None) -> List[Dict]:
        """Synchronous wrapper for discovery."""
        return asyncio.run(self.run_discovery_async(config_paths, limit=limit))

    def run_full_pipeline(self, config_paths: List[str], limit: Optional[int] = None):
        """
        Executes the full E2E flow: Discovery, Alpha, Risk, and Cataloging.
        (Risk optimization and deep cataloging to be integrated in future tasks).
        """
        logger.info("Starting full quantitative pipeline...")

        # 1. Discovery & Alpha
        signals = self.run_discovery(config_paths, limit=limit)

        if not signals:
            logger.warning("No signals generated. Pipeline execution halted.")
            return {"status": "no_signals", "data": []}

        # TODO: Integrate Stage 3 (Risk Optimization)
        # TODO: Integrate Stage 4 (Deep Metadata Verification)

        return {"status": "success", "total_signals": len(signals), "data": signals}
