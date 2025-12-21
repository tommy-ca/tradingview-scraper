import logging
from typing import Dict, List, Optional

from tradingview_scraper.futures_universe_selector import FuturesUniverseSelector, load_config
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

    def run_discovery(self, config_paths: List[str], limit: Optional[int] = None) -> List[Dict]:
        """
        Stage 1 & 2: Discover high-liquidity symbols and apply strategy filters.

        Args:
            config_paths: List of paths to YAML configuration files.
            limit: Optional override for the number of symbols to resolve per config.

        Returns:
            List of dictionaries containing signal data.
        """
        all_signals = []

        for path in config_paths:
            logger.info(f"Running discovery for config: {path}")
            try:
                cfg = load_config(path)
                if limit:
                    cfg.limit = limit
                    cfg.base_universe_limit = limit

                selector = FuturesUniverseSelector(cfg)
                resp = selector.run()

                if resp.get("status") in ["success", "partial_success"]:
                    signals = resp.get("data", [])
                    # Determine direction from filename
                    direction = "LONG" if "short" not in path.lower() else "SHORT"

                    for s in signals:
                        s["direction"] = direction

                    all_signals.extend(signals)
                    logger.info(f"  Generated {len(signals)} signals from {path}.")
                else:
                    err = resp.get("error") or resp.get("errors")
                    logger.warning(f"  Discovery had issues for {path}: {err}")
            except Exception as e:
                logger.error(f"  Discovery failed for {path}: {e}")

        return all_signals

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
