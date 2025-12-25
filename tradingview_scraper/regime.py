import logging
import math
from typing import cast

import numpy as np
import pandas as pd
import pywt
from scipy.stats import entropy

logger = logging.getLogger(__name__)


class MarketRegimeDetector:
    """
    Advanced market regime detector using statistical complexity, volatility clustering,
    and wavelet-based spectral analysis.
    """

    def __init__(self, crisis_threshold: float = 1.8, quiet_threshold: float = 0.7):
        """
        Args:
            crisis_threshold: Weighted score above which regime is CRISIS.
            quiet_threshold: Weighted score below which regime is QUIET.
        """
        self.crisis_threshold = crisis_threshold
        self.quiet_threshold = quiet_threshold

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

    def detect_regime(self, returns: pd.DataFrame) -> str:
        """
        Analyzes the return matrix and classifies the current regime using a
        multi-factor weighted score.

        Returns:
            str: 'QUIET', 'NORMAL', or 'CRISIS'
        """
        if returns.empty or len(returns) < 20:
            return "NORMAL"

        mean_vals = returns.mean(axis=1)
        if isinstance(mean_vals, (float, int)):
            return "NORMAL"

        mean_rets_series = pd.Series(mean_vals)
        market_rets = mean_rets_series.values

        # 1. Volatility Ratio (Shock) - range [0, 3+]
        current_vol = float(mean_rets_series.tail(10).std())
        baseline_vol = float(mean_rets_series.std())
        vol_ratio = current_vol / baseline_vol if baseline_vol > 0 else 1.0

        # 2. Entropy (Complexity) - range [0, 1]
        lookback = min(len(market_rets), 64)
        recent_rets = cast(np.ndarray, market_rets[-lookback:])
        ent = self._permutation_entropy(recent_rets)

        # 3. Vol Clustering (Persistence) - range [0, 1]
        vc = max(0.0, self._volatility_clustering(market_rets))

        # 4. DWT Turbulence (Noise) - range [0, 1]
        turbulence = self._dwt_turbulence(recent_rets)

        # 5. Weighted Regime Score
        # Weights prioritize Vol Shock and Turbulence
        regime_score = (
            0.5 * vol_ratio  # Shock factor
            + 0.5 * turbulence  # Turbulence factor (0-1)
            + 0.3 * vc  # Persistence (0-1)
            + 0.2 * ent  # Complexity (0-1)
        )

        # In a normal market:
        # vol_ratio ~ 1.0, turbulence ~ 0.8, vc ~ 0.1, ent ~ 0.9
        # score ~ 0.5 + 0.4 + 0.03 + 0.18 = 1.11

        # In a quiet market:
        # vol_ratio ~ 0.5, turbulence ~ 0.5, vc ~ 0.0, ent ~ 0.7
        # score ~ 0.25 + 0.25 + 0 + 0.14 = 0.64

        # In a crisis:
        # vol_ratio ~ 2.5, turbulence ~ 0.9, vc ~ 0.4, ent ~ 0.95
        # score ~ 1.25 + 0.45 + 0.12 + 0.19 = 2.01

        logger.info(f"Regime Analysis - Score: {regime_score:.2f} | VolRatio: {vol_ratio:.2f}, Turbulence: {turbulence:.2f}, Clustering: {vc:.2f}, Entropy: {ent:.2f}")

        if regime_score >= self.crisis_threshold:
            return "CRISIS"
        elif regime_score < self.quiet_threshold:
            return "QUIET"
        else:
            return "NORMAL"
