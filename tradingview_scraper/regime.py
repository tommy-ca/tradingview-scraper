import logging
import os
from pathlib import Path
from typing import Dict, Tuple, cast

import numpy as np
import pandas as pd

from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.predictability import (
    calculate_dwt_turbulence,
    calculate_hurst_exponent,
    calculate_permutation_entropy,
    calculate_stationarity_score,
)

logger = logging.getLogger(__name__)


class MarketRegimeDetector:
    """
    Advanced market regime detector using statistical complexity, volatility clustering,
    long-term memory (Hurst), and stationarity (ADF).
    """

    def __init__(
        self,
        crisis_threshold: float = 1.8,
        quiet_threshold: float = 0.7,
        *,
        audit_path: str | Path = "data/lakehouse/regime_audit.jsonl",
        enable_audit_log: bool = True,
    ):
        """
        Args:
            crisis_threshold: Weighted score above which regime is CRISIS.
            quiet_threshold: Weighted score below which regime is QUIET.
        """
        self.crisis_threshold = crisis_threshold
        self.quiet_threshold = quiet_threshold

        # Environment overrides for audit logging hygiene.
        # - `TV_DISABLE_REGIME_AUDIT=1` disables logging entirely.
        # - `TV_REGIME_AUDIT_PATH=/path/to/file.jsonl` overrides the output path.
        if str(os.getenv("TV_DISABLE_REGIME_AUDIT", "")).strip() in {"1", "true", "TRUE", "yes", "YES"}:
            enable_audit_log = False

        env_path = str(os.getenv("TV_REGIME_AUDIT_PATH", "")).strip()
        if env_path:
            audit_path = env_path

        self.enable_audit_log = bool(enable_audit_log)
        self.audit_path = Path(audit_path) if audit_path else None

    def _save_audit_log(
        self,
        regime: str,
        score: float,
        metrics: Dict[str, float | int | str],
        quadrant: str = "UNKNOWN",
    ):
        """Saves detection metadata to the central audit ledger."""
        import datetime
        import json

        if not self.enable_audit_log or self.audit_path is None:
            return

        def _format_metric(value: float | int | str) -> float | int | str:
            if isinstance(value, (int, float, np.number)):
                return round(float(value), 4)
            return value

        entry = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "regime": regime,
            "score": round(score, 4),
            "quadrant": quadrant,
            "metrics": {k: _format_metric(v) for k, v in metrics.items()},
        }
        try:
            self.audit_path.parent.mkdir(parents=True, exist_ok=True)
            with self.audit_path.open("a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to write regime audit log: {e}")

    def _hurst_exponent(self, x: np.ndarray) -> float:
        return calculate_hurst_exponent(x)

    def _stationarity_score(self, x: np.ndarray) -> float:
        return calculate_stationarity_score(x)

    def _permutation_entropy(self, x: np.ndarray, order: int = 3, delay: int = 1) -> float:
        return calculate_permutation_entropy(x, order, delay)

    def _dwt_turbulence(self, returns: np.ndarray) -> float:
        return calculate_dwt_turbulence(returns)

    def _serial_correlation(self, returns: np.ndarray, lags: int = 1) -> float:
        """Measures serial correlation of returns."""
        if len(returns) < lags + 1:
            return 0.0

        s = pd.Series(returns)
        autocorr = s.autocorr(lag=lags)
        return float(abs(autocorr)) if not np.isnan(autocorr) else 0.0

    def _volatility_clustering(self, returns: np.ndarray, lags: int = 5) -> float:
        """
        Measures autocorrelation of absolute returns.
        High values = volatility clustering (regime persistence).
        """
        if len(returns) < lags + 1:
            return 0.0

        abs_rets = pd.Series(np.abs(returns))
        autocorr = abs_rets.autocorr(lag=1)
        return float(autocorr) if not np.isnan(autocorr) else 0.0

    def _hmm_classify(self, x: np.ndarray) -> str:
        """
        Classifies the regime using a 2-state Gaussian Hidden Markov Model.
        Focuses on Volatility (absolute returns).
        States: 0=Quiet, 1=Volatile.
        """
        from hmmlearn.hmm import GaussianHMM

        if len(x) < 40:
            return "NORMAL"

        try:
            # Use absolute returns to focus on volatility clusters
            obs = np.abs(x).reshape(-1, 1)

            # Robust scaling (Standardization)
            obs = (obs - np.mean(obs)) / (np.std(obs) + 1e-12)

            # Initialize and fit HMM (2 states: High Vol vs Low Vol)
            model = GaussianHMM(n_components=2, covariance_type="diag", n_iter=50, random_state=42)
            model.fit(obs)

            # Predict latest state
            hidden_states = model.predict(obs)
            latest_state = int(hidden_states[-1])

            # Map states based on means (High mean = Volatile)
            means = model.means_.flatten()
            if means[latest_state] == np.max(means):
                return "CRISIS"  # High Volatility State
            else:
                return "QUIET"
        except Exception as e:
            logger.debug(f"HMM classification failed: {e}")
            return "NORMAL"

    def detect_quadrant_regime(self, returns: pd.DataFrame) -> Tuple[str, Dict[str, float]]:
        """
        Classifies the market into 4 quadrants inspired by Ray Dalio's All Weather model.
        Axes:
        1. Growth Axis: Annualized Mean Return
        2. Stress Axis: Volatility Ratio (70%) + DWT Turbulence (60%)
        """
        if returns.empty or len(returns) < 20:
            return "STAGNATION", {"growth": 0.0, "stress": 0.0}

        mean_rets = returns.mean(axis=1)
        market_rets = mean_rets.values

        # Axis 1: Growth Axis (Annualized Return)
        ann_return = float(mean_rets.mean() * 252)
        growth_axis = ann_return

        # Axis 2: Stress Axis (Volatility & Noise)
        vol_ratio = float(mean_rets.tail(10).std() / (mean_rets.std() + 1e-12))
        turbulence = calculate_dwt_turbulence(market_rets[-64:])
        stress_axis = (vol_ratio * 0.7) + (turbulence * 0.6)

        # Classification Logic
        if growth_axis > 0.05:  # > 5% annualized
            if stress_axis > 1.1:
                regime = "INFLATIONARY_TREND"
            else:
                regime = "EXPANSION"
        elif growth_axis < -0.05:
            if stress_axis > 1.1:
                regime = "CRISIS"
            else:
                regime = "STAGNATION"
        else:
            regime = "NORMAL"

        metrics = {
            "growth_axis": growth_axis,
            "stress_axis": stress_axis,
            "ann_return": ann_return,
            "vol_ratio": vol_ratio,
            "turbulence": turbulence,
        }

        return regime, metrics

    def detect_regime(self, returns: pd.DataFrame) -> Tuple[str, float]:
        """
        Analyzes the return matrix and classifies the current regime using a
        multi-factor weighted score.

        Returns:
            Tuple[str, float]: ('QUIET'|'NORMAL'|'TURBULENT'|'CRISIS', weighted_score)
        """
        if returns.empty or len(returns) < 20:
            return "NORMAL", 1.0

        mean_vals = returns.mean(axis=1)
        if not isinstance(mean_vals, pd.Series):
            return "NORMAL", 1.0

        mean_rets_series = cast(pd.Series, mean_vals)
        market_rets = cast(np.ndarray, mean_rets_series.values)

        # 1. Volatility Ratio (Shock)
        current_vol = float(mean_rets_series.tail(10).std())
        baseline_vol = float(mean_rets_series.std())
        vol_ratio = current_vol / baseline_vol if baseline_vol > 0 else 1.0

        # 2. Entropy (Complexity)
        lookback = min(len(market_rets), 64)
        recent_rets = cast(np.ndarray, market_rets[-lookback:])
        ent = calculate_permutation_entropy(recent_rets)

        # 3. Vol Clustering (Persistence)
        vc = max(0.0, self._volatility_clustering(market_rets))

        # 4. DWT Turbulence (Noise)
        turbulence = calculate_dwt_turbulence(recent_rets)

        # 5. Hurst Exponent (Memory)
        hurst = calculate_hurst_exponent(market_rets)

        # 6. ADF Stationarity (Trendiness)
        stationarity = calculate_stationarity_score(market_rets)

        # 7. Weighted Regime Score (Sum of weights = 1.0)
        regime_score = (
            0.35 * vol_ratio  # Shock factor
            + 0.25 * turbulence  # Noise factor
            + 0.15 * vc  # Clustering factor
            + 0.10 * ent  # Entropy factor
            + 0.10 * abs(hurst - 0.5) * 2.0  # Deviation from random walk
            + 0.05 * stationarity  # Trend factor
        )

        # 8. Quadrant & HMM
        quadrant, quad_metrics = self.detect_quadrant_regime(returns)
        hmm_regime = self._hmm_classify(market_rets)

        if regime_score >= self.crisis_threshold:
            regime = "CRISIS"
        elif regime_score < self.quiet_threshold:
            regime = "QUIET"
        else:
            regime = "NORMAL"

        # Refined labeling for structural anomalies
        settings = get_settings()
        if settings.features.feat_spectral_regimes:
            # Upgrade to TURBULENT if Hurst/Turbulence signals strong structural shift
            if (turbulence > 0.7 or hurst > 0.65) and regime not in ["CRISIS", "QUIET"]:
                regime = "TURBULENT"

            # HMM and Quadrant confirmation for CRISIS
            if (hmm_regime == "CRISIS" or quadrant == "CRISIS") and regime_score > 1.5:
                regime = "CRISIS"

        # 9. Audit Logging
        full_metrics = {
            "vol_ratio": vol_ratio,
            "turbulence": turbulence,
            "clustering": vc,
            "entropy": ent,
            "hurst": hurst,
            "stationarity": stationarity,
            "hmm_state": hmm_regime,
        }
        full_metrics.update(quad_metrics)
        self._save_audit_log(regime, regime_score, full_metrics, quadrant)

        logger.info(f"Regime: {regime} (Score: {regime_score:.2f}) | Quadrant: {quadrant} | HMM: {hmm_regime}")
        return regime, float(regime_score)
