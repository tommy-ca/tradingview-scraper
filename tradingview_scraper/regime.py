import logging
import os
from pathlib import Path
from typing import Dict, Optional, Tuple, cast

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
    Supports injectable weights for Optuna calibration.
    """

    def __init__(
        self,
        crisis_threshold: float = 1.8,
        quiet_threshold: float = 0.7,
        *,
        audit_path: str | Path = "data/lakehouse/regime_audit.jsonl",
        enable_audit_log: bool = True,
        # CRP-270: Injectable weights
        weights: Optional[Dict[str, float]] = None,
    ):
        self.crisis_threshold = crisis_threshold
        self.quiet_threshold = quiet_threshold

        if str(os.getenv("TV_DISABLE_REGIME_AUDIT", "")).strip() in {"1", "true", "TRUE", "yes", "YES"}:
            enable_audit_log = False

        env_path = str(os.getenv("TV_REGIME_AUDIT_PATH", "")).strip()
        if env_path:
            audit_path = env_path

        self.enable_audit_log = bool(enable_audit_log)
        self.audit_path = Path(audit_path) if audit_path else None

        # CRP-270: Set Weights
        self.weights = weights or {
            "vol_ratio": 0.35,
            "turbulence": 0.25,
            "clustering": 0.15,
            "entropy": 0.10,
            "hurst": 0.10,
            "stationarity": 0.05,
        }

    def _save_audit_log(
        self,
        regime: str,
        score: float,
        metrics: Dict[str, float | int | str],
        quadrant: str = "UNKNOWN",
    ):
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
        h = calculate_hurst_exponent(x)
        return float(h) if h is not None else 0.5

    def _stationarity_score(self, x: np.ndarray) -> float:
        s = calculate_stationarity_score(x)
        return float(s) if s is not None else 0.5

    def _permutation_entropy(self, x: np.ndarray, order: int = 3, delay: int = 1) -> float:
        pe = calculate_permutation_entropy(x, order, delay)
        return float(pe) if pe is not None else 1.0

    def _dwt_turbulence(self, returns: np.ndarray) -> float:
        turb = calculate_dwt_turbulence(returns)
        return float(turb) if turb is not None else 0.5

    def _serial_correlation(self, returns: np.ndarray, lags: int = 1) -> float:
        if len(returns) < lags + 1:
            return 0.0
        s = pd.Series(returns)
        autocorr = s.autocorr(lag=lags)
        return float(abs(autocorr)) if not np.isnan(autocorr) else 0.0

    def _volatility_clustering(self, returns: np.ndarray, lags: int = 1) -> float:
        if len(returns) < lags + 1:
            return 0.0
        abs_rets = pd.Series(np.abs(returns))
        autocorr = abs_rets.autocorr(lag=lags)
        return float(autocorr) if not np.isnan(autocorr) else 0.0

    def _hmm_classify(self, x: np.ndarray) -> str:
        from hmmlearn.hmm import GaussianHMM

        if len(x) < 40:
            return "NORMAL"
        try:
            obs = np.abs(x).reshape(-1, 1)
            obs_std = np.std(obs)
            if obs_std > 1e-12:
                obs = (obs - np.mean(obs)) / (obs_std + 1e-12)
            else:
                obs = obs - np.mean(obs)
            model = GaussianHMM(n_components=2, covariance_type="diag", n_iter=50, random_state=42)
            model.fit(obs)
            hidden_states = model.predict(obs)
            latest_state = int(hidden_states[-1])
            means = model.means_.flatten()
            return "CRISIS" if means[latest_state] == np.max(means) else "QUIET"
        except Exception:
            return "NORMAL"

    def detect_quadrant_regime(self, returns: pd.DataFrame) -> Tuple[str, Dict[str, float]]:
        if returns.empty or len(returns) < 20:
            return "STAGNATION", {"growth": 0.0, "stress": 0.0}
        mean_rets = cast(pd.Series, returns.mean(axis=1)).dropna()
        if len(mean_rets) < 20:
            return "STAGNATION", {"growth": 0.0, "stress": 0.0}
        market_rets = cast(np.ndarray, mean_rets.values)
        ann_return = float(mean_rets.mean() * 252)
        tail_slice = mean_rets.tail(10)
        tail_std = float(tail_slice.std()) if len(tail_slice.dropna()) > 1 else 0.0
        full_std = float(mean_rets.std()) if len(mean_rets.dropna()) > 1 else 1.0
        vol_ratio = float(tail_std / (full_std + 1e-12))
        turbulence = self._dwt_turbulence(market_rets[-64:])
        stress_axis = (vol_ratio * 0.7) + (turbulence * 0.6)
        if ann_return > 0.05:
            regime = "INFLATIONARY_TREND" if stress_axis > 1.1 else "EXPANSION"
        elif ann_return < -0.05:
            regime = "CRISIS" if stress_axis > 1.1 else "STAGNATION"
        else:
            regime = "NORMAL"
        return regime, {"growth_axis": ann_return, "stress_axis": stress_axis, "ann_return": ann_return, "vol_ratio": vol_ratio, "turbulence": turbulence}

    def detect_regime(self, returns: pd.DataFrame) -> Tuple[str, float, str]:
        if returns.empty or len(returns) < 20:
            return "NORMAL", 1.0, "NORMAL"
        mean_rets_series = cast(pd.Series, returns.mean(axis=1)).dropna()
        if len(mean_rets_series) < 20:
            return "NORMAL", 1.0, "NORMAL"
        market_rets = cast(np.ndarray, mean_rets_series.values)
        tail_slice = mean_rets_series.tail(10)
        current_vol = float(tail_slice.std()) if len(tail_slice.dropna()) > 1 else 0.0
        baseline_vol = float(mean_rets_series.std()) if len(mean_rets_series.dropna()) > 1 else 1.0
        vol_ratio = current_vol / (baseline_vol + 1e-12)

        ent = self._permutation_entropy(market_rets[-64:])
        vc = max(0.0, self._volatility_clustering(market_rets))
        turbulence = self._dwt_turbulence(market_rets[-64:])
        hurst = self._hurst_exponent(market_rets)
        stationarity = self._stationarity_score(market_rets)

        # CRP-270: Weighted Score using injectable weights
        regime_score = (
            self.weights["vol_ratio"] * vol_ratio
            + self.weights["turbulence"] * turbulence
            + self.weights["clustering"] * vc
            + self.weights["entropy"] * ent
            + self.weights["hurst"] * abs(hurst - 0.5) * 2.0
            + self.weights["stationarity"] * stationarity
        )

        quadrant, quad_metrics = self.detect_quadrant_regime(returns)
        hmm_regime = self._hmm_classify(market_rets)

        if regime_score >= self.crisis_threshold:
            regime = "CRISIS"
        elif regime_score < self.quiet_threshold:
            regime = "QUIET"
        else:
            regime = "NORMAL"

        settings = get_settings()
        if settings.features.feat_spectral_regimes:
            if (turbulence > 0.7 or hurst > 0.65) and regime not in ["CRISIS", "QUIET"]:
                regime = "TURBULENT"
            if (hmm_regime == "CRISIS" or quadrant == "CRISIS") and regime_score > 1.5:
                regime = "CRISIS"

        full_metrics = {"vol_ratio": vol_ratio, "turbulence": turbulence, "clustering": vc, "entropy": ent, "hurst": hurst, "stationarity": stationarity, "hmm_state": hmm_regime, **quad_metrics}
        self._save_audit_log(regime, regime_score, full_metrics, quadrant)
        logger.info(f"Regime: {regime} (Score: {regime_score:.2f}) | Quadrant: {quadrant} | HMM: {hmm_regime}")
        return regime, float(regime_score), quadrant
