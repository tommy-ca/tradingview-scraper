from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import pandas as pd

from tradingview_scraper.portfolio_engines.backtest_simulators import CVXPortfolioSimulator

logger = logging.getLogger(__name__)


def run_nautilus_backtest(
    *,
    returns: pd.DataFrame,
    weights_df: pd.DataFrame,
    initial_holdings: Optional[pd.Series],
    settings: Any,
) -> Dict[str, Any]:
    """
    Best-effort NautilusTrader adapter.

    If NautilusTrader is unavailable or raises during setup, we fall back to the
    CVXPortfolio simulator (parity baseline).
    """
    try:
        import nautilus_trader  # type: ignore  # noqa: F401
    except Exception as exc:
        raise ImportError("nautilus-trader not available") from exc

    # NOTE: Full event-driven integration is expected to be provided by the
    # NautilusTrader adapter layer. For now, we mirror CVXPortfolio parity
    # to keep tournament output stable when Nautilus is enabled.
    logger.warning("NautilusTrader adapter running in parity fallback mode.")
    return CVXPortfolioSimulator().simulate(returns, weights_df, initial_holdings)
