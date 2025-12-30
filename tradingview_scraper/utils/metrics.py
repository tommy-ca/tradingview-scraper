import numpy as np
import pandas as pd
from typing import Dict, Any, Optional


def calculate_performance_metrics(daily_returns: pd.Series) -> Dict[str, Any]:
    """
    Computes a standardized suite of performance metrics from a daily returns series.

    Assumes daily returns are simple returns (not log).
    """
    empty_res = {
        "total_return": 0.0,
        "realized_vol": 0.0,
        "sharpe": 0.0,
        "max_drawdown": 0.0,
        "var_95": None,
        "cvar_95": None,
    }

    if daily_returns.empty:
        return empty_res

    # Clean returns
    rets = daily_returns.dropna()
    if len(rets) == 0:
        return empty_res

    # 1. Basic Returns
    total_return = (1 + rets).prod() - 1

    # 2. Volatility (Annualized)
    # Epsilon guard for zero vol
    vol_daily = rets.std()
    realized_vol = vol_daily * np.sqrt(252)

    # 3. Sharpe Ratio
    # (Mean Return / Vol) * sqrt(252)
    # We use 1e-9 guard for zero vol cases
    sharpe = (rets.mean() * 252) / (realized_vol + 1e-9)

    # 4. Drawdown
    cum_ret = (1 + rets).cumprod()
    running_max = cum_ret.cummax()
    drawdown = (cum_ret - running_max) / (running_max + 1e-12)
    max_drawdown = float(drawdown.min())

    # 5. Tail Risk (95% Confidence)
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
    }
