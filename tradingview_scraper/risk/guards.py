from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
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
    # Prop-firm logic: Loss is measured against the starting balance/equity snapshot.
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
    Global circuit breaker if total account value drops too low.
    """
    if context.starting_balance <= 0:
        return None

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


def check_cluster_caps(context: RiskContext, weights: dict[str, float], clusters: dict[str, list[str]], cap: float = 0.25) -> list[RiskEvent]:
    """
    Enforces Level 2: Correlation Guard (Cluster Caps).
    Ensures no single volatility cluster dominates the portfolio.
    """
    events = []
    cluster_weights = {}

    for cid, members in clusters.items():
        total_w = sum(abs(weights.get(m, 0.0)) for m in members)
        cluster_weights[cid] = total_w

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
    Standard Kelly: f* = (bp - q) / b = p - (1-p)/R
    Prop-Firm Safety: f* * fraction (default 1/10th Kelly).
    """
    if payoff_ratio <= 0:
        return weights * 0.0

    # Kelly formula
    p = win_rate
    R = payoff_ratio
    kelly_full = p - ((1 - p) / R)

    # Apply safety fraction and floor at 0
    multiplier = max(0.0, kelly_full * fraction)

    # Scale all weights by the Kelly multiplier
    return weights * multiplier
