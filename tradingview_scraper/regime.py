import logging
import math
from typing import Dict, Tuple, cast

import numpy as np
import pandas as pd
import pywt  # type: ignore
from scipy.stats import entropy
from statsmodels.tsa.stattools import adfuller

from tradingview_scraper.settings import get_settings

logger = logging.getLogger(__name__)


class MarketRegimeDetector:
    """
    Advanced market regime detector using statistical complexity, volatility clustering,
    long-term memory (Hurst), and stationarity (ADF).
    """

    def __init__(self, crisis_threshold: float = 1.7, quiet_threshold: float = 1.3):
        """
        Args:
            crisis_threshold: Weighted score above which regime is CRISIS.
            quiet_threshold: Weighted score below which regime is QUIET.
        """
        self.crisis_threshold = crisis_threshold
        self.quiet_threshold = quiet_threshold

    def _hurst_exponent(self, x: np.ndarray) -> float:
        """
        Calculates the Hurst Exponent using Rescaled Range (R/S) analysis.
        Simplified version for short-to-medium windows.
        """
        if len(x) < 30:
            return 0.5

        try:
            # Create a range of lags
            lags = [5, 10, 15, 20, 25, 30]
            lags = [l for l in lags if l < len(x) // 2]

            # Calculate the variance of the difference for each lag
            # Var(x(t+k) - x(t)) ~ k^(2H)
            tau = []
            for lag in lags:
                diff = x[lag:] - x[:-lag]
                tau.append(np.std(diff))

            # Linear regression on log-log scale
            poly = np.polyfit(np.log(lags), np.log(tau), 1)
            # Slope is H
            h_val = float(poly[0])

            # Clamp to [0, 1]
            return float(np.clip(h_val, 0.0, 1.0))
        except Exception:
            return 0.5

    def _stationarity_score(self, x: np.ndarray) -> float:
        """
        Uses Augmented Dickey-Fuller (ADF) test to measure stationarity.
        Returns a score in [0, 1] where 1.0 is highly non-stationary/trending.
        """
        if len(x) < 20:
            return 0.5

        try:
            # p-value: probability that the process has a unit root (non-stationary)
            result = adfuller(x)
            p_value = float(result[1])
            return p_value  # High p-value = non-stationary
        except Exception:
            return 0.5

    def _serial_correlation(self, returns: np.ndarray, lags: int = 1) -> float:
        """Measures serial correlation of returns."""
        if len(returns) < lags + 1:
            return 0.0

        s = pd.Series(returns)
        autocorr = s.autocorr(lag=lags)
        return float(abs(autocorr)) if not np.isnan(autocorr) else 0.0

    def _permutation_entropy(self, x: np.ndarray, order: int = 3, delay: int = 1) -> float:
        """
        Calculates Permutation Entropy as a measure of structural randomness.
        Low values = ordered/trending, High values = noisy/random.
        """
        if len(x) < order:
            return 1.0

        n = len(x) - (order - 1) * delay
        permutations = []
        for i in range(n):
            segment = x[i : i + order * delay : delay]
            perm = tuple(np.argsort(segment))
            permutations.append(perm)

        _, counts = np.unique(permutations, axis=0, return_counts=True)
        probs = counts / len(permutations)
        pe_val = float(entropy(probs))
        return float(pe_val / math.log(math.factorial(order)))

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

    def _dwt_turbulence(self, returns: np.ndarray) -> float:
        """
        Uses Discrete Wavelet Transform to measure high-frequency 'turbulence'.
        Returns a value in [0, 1] representing the fraction of energy in noise.
        """
        if len(returns) < 8:
            return 0.5

        coeffs = pywt.wavedec(returns, "haar", level=min(3, pywt.dwt_max_level(len(returns), "haar")))
        cA = coeffs[0]
        cD = np.concatenate(coeffs[1:])

        energy_approx = np.sum(np.square(cA))
        energy_detail = np.sum(np.square(cD))
        total_energy = energy_approx + energy_detail

        if total_energy == 0:
            return 0.5

        return float(energy_detail / total_energy)

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
            # Use diagonal covariance for better stability
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
                return "NORMAL"
        except Exception as e:
            logger.debug(f"HMM classification failed: {e}")
            return "NORMAL"

    def detect_quadrant_regime(self, returns: pd.DataFrame) -> Tuple[str, Dict[str, float]]:
        """
        Classifies the market into 4 quadrants inspired by Ray Dalio's All Weather model.
        Axes:
        1. Growth Proxy (Return): Annualized Mean Return
        2. Stress Proxy (Inflation/Risk): Volatility Ratio + DWT Turbulence
        """
        if returns.empty or len(returns) < 20:
            return "STAGNATION", {"growth": 0.0, "stress": 0.0}

        mean_rets = returns.mean(axis=1)
        market_rets = mean_rets.values

        # Axis 1: Growth Axis (Annualized Return)
        # > 0: Growth, < 0: Contraction
        ann_return = float(mean_rets.mean() * 252)
        growth_axis = ann_return

        # Axis 2: Stress Axis (Volatility & Noise)
        # > 1.0: Rising Stress, < 1.0: Falling Stress
        vol_ratio = float(mean_rets.tail(10).std() / (mean_rets.std() + 1e-12))
        turbulence = self._dwt_turbulence(market_rets[-64:])
        # 1.0 is the neutral stress point
        stress_axis = (vol_ratio * 0.7) + (turbulence * 0.6)

        # Classification Logic
        if growth_axis > 0.05:  # > 5% annualized
            if stress_axis > 1.1:
                regime = "INFLATIONARY_TREND"  # High Growth, High Stress
            else:
                regime = "EXPANSION"  # High Growth, Low Stress (Bull)
        elif growth_axis < -0.05:  # < -5% annualized
            if stress_axis > 1.1:
                regime = "CRISIS"  # Low Growth, High Stress (Crash)
            else:
                regime = "STAGNATION"  # Low Growth, Low Stress (Bear/Quiet)
        else:
            regime = "NORMAL"  # Neutral zone

        metrics = {"growth_axis": growth_axis, "stress_axis": stress_axis, "ann_return": ann_return, "vol_ratio": vol_ratio, "turbulence": turbulence}

        logger.info(f"Quadrant Analysis: {regime} | Growth: {growth_axis:.2%}, Stress: {stress_axis:.2f}")
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
        ent = self._permutation_entropy(recent_rets)

        # 3. Vol Clustering (Persistence)
        vc = max(0.0, self._volatility_clustering(market_rets))

        # 4. DWT Turbulence (Noise)
        turbulence = self._dwt_turbulence(recent_rets)

        # 5. Hurst Exponent (Memory)
        hurst = self._hurst_exponent(market_rets)

        # 6. ADF Stationarity (Trendiness)
        stationarity = self._stationarity_score(market_rets)

        # 7. Serial Correlation
        sc = self._serial_correlation(market_rets)

        # 8. Weighted Regime Score
        # Now incorporating Hurst and Stationarity for better trend/noise detection
        regime_score = (
            0.4 * vol_ratio  # Shock factor
            + 0.3 * turbulence  # Noise factor
            + 0.2 * vc  # Clustering factor
            + 0.1 * ent  # Entropy factor
            + 0.1 * stationarity  # Trend factor
            + 0.1 * abs(hurst - 0.5) * 2.0  # Deviation from random walk
        )

        logger.info(f"Regime Analysis - Score: {regime_score:.2f} | VolRatio: {vol_ratio:.2f}, Turbulence: {turbulence:.2f}, Clustering: {vc:.2f}, Hurst: {hurst:.2f}, ADF: {stationarity:.2f}")

        # 9. HMM Classification (Secondary Vote)
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
            # Transition to TURBULENT if Hurst is very high (trending) or Turbulence is high
            if (turbulence > 0.7 or hurst > 0.65) and regime != "CRISIS":
                regime = "TURBULENT"
                logger.info(f"Regime upgraded to TURBULENT (Hurst={hurst:.2f}, Turb={turbulence:.2f})")

            # HMM override for strong trends
            if hmm_regime == "TURBULENT" and regime == "NORMAL" and hurst > 0.55:
                regime = "TURBULENT"
                logger.info("HMM confirmed Bullish/Trend regime.")

            # HMM confirmation for CRISIS
            if hmm_regime == "CRISIS" and regime == "TURBULENT":
                regime = "CRISIS"
                logger.info("HMM upgraded TURBULENT to CRISIS.")

        return regime, float(regime_score)
