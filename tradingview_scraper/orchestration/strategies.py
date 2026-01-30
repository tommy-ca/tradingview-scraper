from tradingview_scraper.settings import TradingViewScraperSettings


class StrategyResolver:
    """
    Resolves the strategy type for a given execution context.
    Decouples strategy inference from the main BacktestEngine.
    """

    @staticmethod
    def resolve_strategy(settings: TradingViewScraperSettings) -> str:
        """
        Determines the strategy type.

        Priority:
        1. Manifest/Env Configuration (settings.strategy_type)
        2. Profile Name Inference (Legacy Fallback)
        3. Default ("trend_following")
        """

        # 1. Manifest/Env Configuration
        if settings.strategy_type:
            return settings.strategy_type

        # 2. Profile Name Inference (Legacy)
        profile = (settings.profile or "").lower()
        if "mean_rev" in profile or "meanrev" in profile:
            return "mean_reversion"
        elif "breakout" in profile:
            return "breakout"

        # 3. Default
        return "trend_following"
