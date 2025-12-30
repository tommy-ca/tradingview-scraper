from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def calculate_performance_metrics(daily_returns: pd.Series) -> Dict[str, Any]:
    """
    Computes a standardized suite of performance metrics using QuantStats.
    Ensures mathematical consistency across all simulators and reports.
    """
    empty_res = {
        "total_return": 0.0,
        "realized_vol": 0.0,
        "sharpe": 0.0,
        "max_drawdown": 0.0,
        "var_95": None,
        "cvar_95": None,
        "sortino": 0.0,
        "calmar": 0.0,
        "omega": 0.0,
    }

    if daily_returns.empty:
        return empty_res

    # Clean returns
    rets = daily_returns.dropna()
    if len(rets) == 0:
        return empty_res

    try:
        import quantstats as qs

        # 1. Basic Returns
        total_return = (1 + rets).prod() - 1

        # 2. Annualized Vol
        realized_vol = float(qs.stats.volatility(rets, annualize=True))

        # 3. Sharpe Ratio (Annualized)
        sharpe = float(qs.stats.sharpe(rets, rf=0.0))

        # 4. Drawdown
        max_drawdown = float(qs.stats.max_drawdown(rets))

        # 5. Tail Risk (95% Confidence)
        var_95 = float(qs.stats.value_at_risk(rets, sigma=1, confidence=0.95))
        cvar_95 = float(qs.stats.expected_shortfall(rets, sigma=1, confidence=0.95))

        # 6. Advanced Stats
        sortino = float(qs.stats.sortino(rets, rf=0.0))
        calmar = float(qs.stats.calmar(rets))
        omega = float(qs.stats.omega(rets))

        return {
            "total_return": float(total_return),
            "annualized_return": float(rets.mean() * 252),
            "realized_vol": float(realized_vol),
            "sharpe": float(sharpe),
            "max_drawdown": float(max_drawdown),
            "var_95": float(var_95),
            "cvar_95": float(cvar_95),
            "sortino": sortino,
            "calmar": calmar,
            "omega": omega,
        }

    except Exception as e:
        logger.error(f"QuantStats calculation failed: {e}. Falling back to basic math.")
        # Fallback to internal basic math if QuantStats fails or isn't installed
        total_return = (1 + rets).prod() - 1
        vol_daily = rets.std()
        realized_vol = vol_daily * np.sqrt(252)
        sharpe = (rets.mean() * 252) / (realized_vol + 1e-9)
        cum_ret = (1 + rets).cumprod()
        running_max = cum_ret.cummax()
        drawdown = (cum_ret - running_max) / (running_max + 1e-12)
        max_drawdown = float(drawdown.min())
        var_95 = float(rets.quantile(0.05))
        tail = rets[rets <= var_95]
        cvar_95 = float(tail.mean()) if len(tail) > 0 else var_95

        return {
            "total_return": float(total_return),
            "realized_vol": float(realized_vol),
            "sharpe": float(sharpe),
            "max_drawdown": float(max_drawdown),
            "var_95": float(var_95),
            "cvar_95": float(cvar_95),
            "sortino": 0.0,
            "calmar": 0.0,
            "omega": 0.0,
        }
