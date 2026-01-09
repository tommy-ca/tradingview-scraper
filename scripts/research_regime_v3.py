import json
import logging
import os
import sys
from typing import Dict, Optional, cast

import numpy as np
import pandas as pd

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingview_scraper.regime import MarketRegimeDetector
from tradingview_scraper.utils.metrics import calculate_max_drawdown

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("research_regime_v3")


def calculate_tail_risk_metrics(returns: pd.DataFrame) -> Dict[str, float]:
    """Calculates tail risk metrics for the portfolio."""
    metrics = {}
    if returns.empty:
        return metrics

    # Portfolio-level returns (equal weight for estimation)
    port_ret = returns.mean(axis=1)

    # Max Drawdown
    mdd = calculate_max_drawdown(port_ret)
    metrics["max_drawdown"] = float(mdd)

    # VaR (95%)
    var_95 = np.percentile(port_ret, 5)
    metrics["var_95"] = float(var_95)

    # CVaR (95%) - Expected Shortfall
    cvar_95 = port_ret[port_ret <= var_95].mean()
    metrics["cvar_95"] = float(cvar_95)

    # Tail-Risk Mitigation Metric (TRM): Inverse of MDD adjusted for volatility
    vol = port_ret.std() * np.sqrt(252)
    metrics["trm_score"] = float(1.0 / (mdd * vol)) if mdd > 0 and vol > 0 else 0.0

    # Skewness and Kurtosis
    metrics["skew"] = float(port_ret.skew())
    metrics["kurtosis"] = float(port_ret.kurtosis())

    return metrics


def calculate_alpha_capture_metrics(returns: pd.DataFrame) -> Dict[str, float]:
    """Calculates metrics related to alpha capture potential."""
    metrics = {}
    if returns.empty:
        return metrics

    # Momentum strength (avg absolute return)
    # High momentum environments are better for alpha capture
    metrics["momentum_strength"] = float(returns.abs().mean().mean())

    # Dispersion (cross-sectional std dev)
    # Higher dispersion = more opportunities for alpha
    metrics["dispersion"] = float(returns.std(axis=1).mean())

    # Alpha Capture Efficiency (ACE): Returns adjusted for turnover proxy (dispersion)
    metrics["ace_score"] = float(returns.mean().mean() / (metrics["dispersion"] + 1e-6))

    return metrics


def research_regime_v3():
    returns_path = "data/lakehouse/portfolio_returns.pkl"
    if not os.path.exists(returns_path):
        logger.error("Returns matrix missing.")
        return

    returns = cast(pd.DataFrame, pd.read_pickle(returns_path))
    logger.info(f"Loaded returns matrix with shape: {returns.shape}")

    detector = MarketRegimeDetector()

    # 1. Regime Detection
    regime, regime_score = detector.detect_regime(returns)
    logger.info(f"Market Regime: {regime} (Score: {regime_score:.2f})")

    # 2. Tail Risk Analysis
    tail_risk = calculate_tail_risk_metrics(returns)
    logger.info("Tail Risk Metrics:")
    for k, v in tail_risk.items():
        logger.info(f"  - {k}: {v:.4f}")

    # 3. Alpha Capture Analysis
    alpha_metrics = calculate_alpha_capture_metrics(returns)
    logger.info("Alpha Capture Potential:")
    for k, v in alpha_metrics.items():
        logger.info(f"  - {k}: {v:.4f}")

    # 4. Persistence Integration
    persistence_path = "data/lakehouse/persistence_metrics.json"
    median_duration: Optional[float] = None

    if os.path.exists(persistence_path):
        with open(persistence_path, "r") as f:
            persistence_data = json.load(f)

        # Calculate population median duration if available
        durations = [x["trend_duration"] for x in persistence_data if x.get("regime") in ["STRONG_TREND", "TRENDING"]]
        if durations:
            median_duration = float(np.median(durations))
            logger.info(f"Median Trend Duration (Persistence): {median_duration:.1f} days")

            # Recommendation Logic - Nyquist sampling (duration / 2)
            recommended_window = max(5, int(median_duration / 2))
            logger.info(f"Recommended Rebalance Window (Nyquist): {recommended_window} days")
        else:
            logger.warning("No trend durations found in persistence data.")
            # Default fallback if no trends found
            recommended_window = 20
    else:
        logger.warning("Persistence metrics not found. Run 'make research-persistence' first.")
        recommended_window = 20  # Default

    # Save Enhanced Analysis
    analysis_output = {
        "regime": {"label": regime, "score": regime_score},
        "tail_risk": tail_risk,
        "alpha_capture": alpha_metrics,
        "persistence": {"median_trend_duration": median_duration, "recommended_window": recommended_window},
        "timestamp": pd.Timestamp.now().isoformat(),
    }

    output_path = "data/lakehouse/regime_analysis_v3.json"
    with open(output_path, "w") as f:
        json.dump(analysis_output, f, indent=2)
    logger.info(f"Enhanced regime analysis saved to {output_path}")


if __name__ == "__main__":
    research_regime_v3()
