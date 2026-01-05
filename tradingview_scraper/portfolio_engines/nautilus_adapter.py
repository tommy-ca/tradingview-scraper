from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import pandas as pd

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

    This is intended to be an *independent* simulator for parity checks against
    CVXPortfolio. Until a full event-driven integration is implemented, we run
    a deterministic trade-based simulator so that parity metrics are meaningful
    (i.e., not trivially identical to CVXPortfolio).
    """
    try:
        import nautilus_trader  # type: ignore  # noqa: F401
    except Exception:
        # NautilusTrader is optional; parity checks can still run without the
        # external dependency present.
        pass

    from tradingview_scraper.portfolio_engines.backtest_simulators import ReturnsSimulator

    return ReturnsSimulator().simulate(returns, weights_df, initial_holdings)
