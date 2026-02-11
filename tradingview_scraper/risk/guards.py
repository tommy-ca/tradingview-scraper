from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    import pandas as pd
    from tradingview_scraper.risk.models import RiskContext

from tradingview_scraper.risk.models import RiskEvent

logger = logging.getLogger("risk.guards")


def check_account_mdd(context: RiskContext) -> Optional[RiskEvent]:
    """
    Enforces Level 1: Max Daily Drawdown (MDD).
    Calculates drawdown from the daily starting equity (UTC 00:00 snapshot).
    """
    if context.daily_starting_equity <= 0:
        return None

    # Calculate drawdown from starting equity of the day
    # Prop-firm logic: Baseline is the start of the day.
    daily_dd = (context.current_equity - context.daily_starting_equity) / context.daily_starting_equity

    if daily_dd <= -context.max_daily_loss_pct:
        return RiskEvent(
            trigger="MAX_DAILY_DRAWDOWN",
            action="FLATTEN",
            value_at_trigger=context.current_equity,
            threshold_violated=context.max_daily_loss_pct,
            metadata={"daily_dd": daily_dd, "starting_equity": context.daily_starting_equity},
        )

    return None


def check_equity_guard(context: RiskContext) -> Optional[RiskEvent]:
    """
    Enforces Level 1: Max Total Loss (Equity Guard).
    Global circuit breaker if total account value drops below the absolute hard limit.
    """
    if context.starting_balance <= 0:
        return None

    # Overall drawdown from initial capital pool
    total_dd = (context.current_equity - context.starting_balance) / context.starting_balance

    if total_dd <= -context.max_total_loss_pct:
        return RiskEvent(
            trigger="GLOBAL_EQUITY_GUARD",
            action="FLATTEN",
            value_at_trigger=context.current_equity,
            threshold_violated=context.max_total_loss_pct,
            metadata={"total_dd": total_dd, "starting_balance": context.starting_balance},
        )

    return None


def check_cluster_caps(context: RiskContext, weights: dict[str, float], clusters: dict[str, list[str]], cap: float = 0.25) -> List[RiskEvent]:
    """
    Enforces Level 2: Correlation Guard (Cluster Caps).
    Ensures no single volatility cluster (Pillar 1) dominates the portfolio.
    """
    events = []
    for cid, members in clusters.items():
        total_w = sum(abs(weights.get(m, 0.0)) for m in members)

        if total_w > cap:
            events.append(
                RiskEvent(
                    trigger="CLUSTER_CAP_BREACH",
                    action="SCALE",
                    value_at_trigger=total_w,
                    threshold_violated=cap,
                    metadata={"cluster_id": cid, "members": members},
                )
            )

    return events


def apply_kelly_scaling(weights: pd.Series, win_rate: float, payoff_ratio: float, fraction: float = 0.1) -> pd.Series:
    """
    Applies prop-firm adjusted Kelly Criterion scaling.
    Standard Kelly: f* = p - (1-p)/R
    Prop-Firm Safety: Uses fractional Kelly (default 1/10th) to ensure compliance.
    """
    if payoff_ratio <= 0:
        return weights * 0.0

    # Kelly formula
    p = win_rate
    R = payoff_ratio
    kelly_full = p - ((1 - p) / R)

    # Apply safety fraction (conservative institutional standard)
    multiplier = max(0.0, kelly_full * fraction)

    return weights * multiplier
