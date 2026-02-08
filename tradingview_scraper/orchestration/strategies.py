import logging
from typing import Optional

logger = logging.getLogger(__name__)


class StrategyFactory:
    """Factory for determining strategy type from profile configuration."""

    @staticmethod
    def infer_strategy(profile_name: str, config_strategy: Optional[str] = None) -> str:
        """
        Infers the strategy type.
        Priority:
        1. Explicit strategy in config.
        2. Inferred from profile name (legacy fallback).
        3. Default to 'trend_following'.
        """
        if config_strategy:
            return config_strategy

        logger.warning(f"DEPRECATION: Profile '{profile_name}' relies on name-based strategy inference. Please add an explicit 'strategy' field to manifest.json.")

        p_name = profile_name.lower()
        if "mean_rev" in p_name or "meanrev" in p_name:
            return "mean_reversion"
        elif "breakout" in p_name:
            return "breakout"

        return "trend_following"
