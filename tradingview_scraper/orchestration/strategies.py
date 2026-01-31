import json
import logging

from tradingview_scraper.settings import TradingViewScraperSettings

logger = logging.getLogger("orchestration.strategies")


class StrategyResolver:
    """
    Decouples strategy configuration from execution logic.
    Supports manifest-driven configuration and legacy fallback.
    """

    @staticmethod
    def resolve_strategy(config: TradingViewScraperSettings) -> str:
        """
        Determines the strategy type based on configuration.
        Priority:
        1. Manifest/Config explicit setting ('strategy_type')
        2. Legacy inference from profile name (for backward compatibility)
        3. Default ('trend_following')
        """

        # 1. Check explicit config
        if hasattr(config, "strategy_type") and config.strategy_type:
            return config.strategy_type

        # 2. Legacy Inference
        global_profile = config.profile or ""
        profile_lower = global_profile.lower()

        if "mean_rev" in profile_lower or "meanrev" in profile_lower:
            return "mean_reversion"
        elif "breakout" in profile_lower:
            return "breakout"
        elif "vol_breakout" in profile_lower:
            return "vol_breakout"

        # 3. Default
        return "trend_following"

    @staticmethod
    def is_meta_profile(config: TradingViewScraperSettings) -> bool:
        """
        Checks if the current profile corresponds to a meta-portfolio.
        """
        manifest_path = config.manifest_path
        if not manifest_path.exists():
            return False

        try:
            with open(manifest_path, "r") as f:
                manifest = json.load(f)
            prof_cfg = manifest.get("profiles", {}).get(config.profile, {})
            return "sleeves" in prof_cfg
        except Exception as e:
            logger.warning(f"Failed to check meta profile status: {e}")
            return False
