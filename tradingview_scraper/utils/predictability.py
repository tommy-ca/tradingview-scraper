import logging
import math

import numpy as np
import pywt
from scipy.stats import entropy
from statsmodels.tsa.stattools import adfuller

logger = logging.getLogger(__name__)


def calculate_hurst_exponent(x: np.ndarray) -> float:
    """
    Calculates the Hurst Exponent using Rescaled Range (R/S) analysis.
    Values:
    - H > 0.5: Trending (Persistent)
    - H < 0.5: Mean-reverting (Anti-persistent)
    - H = 0.5: Random Walk (Brownian Motion)
    """
    if len(x) < 32:
        return 0.5

    try:

        def get_rs(series):
            # Range / Standard Deviation
            m = np.mean(series)
            z = np.cumsum(series - m)
            r = np.max(z) - np.min(z)
            s = np.std(series)
            return r / s if s > 0 else 0

        # Divide into segments
        n_total = len(x)
        # Use logarithmic scales for lags
        lags = [2**i for i in range(3, 10)]  # 8, 16, 32, 64, 128, 256, 512
        lags = [l for l in lags if l <= n_total // 2]

        if len(lags) < 2:
            # Fallback to linear lags if series is short
            lags = [10, 15, 20, 25]
            lags = [l for l in lags if l <= n_total // 2]

        rs_values = []
        valid_lags = []

        for l in lags:
            n_segments = n_total // l
            rs_avg = []
            for i in range(n_segments):
                segment = x[i * l : (i + 1) * l]
                rs = get_rs(segment)
                if rs > 0:
                    rs_avg.append(rs)
            if rs_avg:
                rs_values.append(np.mean(rs_avg))
                valid_lags.append(l)

        if len(rs_values) < 2:
            return 0.5

        # Hurst exponent is the slope of log(R/S) vs log(n)
        poly = np.polyfit(np.log(valid_lags), np.log(rs_values), 1)
        return float(np.clip(poly[0], 0.0, 1.0))
    except Exception as e:
        logger.debug(f"Hurst calculation failed: {e}")
        return 0.5


def calculate_permutation_entropy(x: np.ndarray, order: int = 3, delay: int = 1) -> float:
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

    # Normalize by log(n!) which is the maximum possible entropy for order n
    return float(pe_val / math.log(math.factorial(order)))


def calculate_efficiency_ratio(returns: np.ndarray) -> float:
    """
    Calculates Kaufman's Efficiency Ratio (ER).
    ER = |Total Change| / Sum of Absolute Changes

    Higher ER (approaching 1.0) indicates a more efficient trend.
    Lower ER (approaching 0.0) indicates high noise/chop.
    """
    if len(returns) < 2:
        return 0.0

    # Net cumulative return
    net_change = abs(np.sum(returns))

    # Total path length (sum of absolute returns)
    path_length = np.sum(np.abs(returns))

    if path_length == 0:
        return 0.0

    return float(net_change / path_length)


def calculate_dwt_turbulence(returns: np.ndarray) -> float:
    """
    Uses Discrete Wavelet Transform to measure high-frequency 'turbulence'.
    Returns a value in [0, 1] representing the fraction of energy in noise.
    """
    if len(returns) < 8:
        return 0.5

    try:
        coeffs = pywt.wavedec(returns, "haar", level=min(3, pywt.dwt_max_level(len(returns), "haar")))
        cA = coeffs[0]
        cD = np.concatenate(coeffs[1:])

        energy_approx = np.sum(np.square(cA))
        energy_detail = np.sum(np.square(cD))
        total_energy = energy_approx + energy_detail

        if total_energy == 0:
            return 0.5

        return float(energy_detail / total_energy)
    except Exception as e:
        logger.debug(f"DWT calculation failed: {e}")
        return 0.5


def calculate_stationarity_score(returns: np.ndarray) -> float:
    """
    Uses Augmented Dickey-Fuller (ADF) test to measure stationarity.
    Returns a score in [0, 1] where 1.0 is highly non-stationary/trending.
    """
    if len(returns) < 20:
        return 0.5

    try:
        # p-value: probability that the process has a unit root (non-stationary)
        result = adfuller(returns)
        p_value = float(result[1])
        return p_value  # High p-value = non-stationary
    except Exception as e:
        logger.debug(f"ADF test failed: {e}")
        return 0.5
