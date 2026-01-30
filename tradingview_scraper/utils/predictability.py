import logging
import math
from typing import Dict, Optional

import numpy as np
import pywt
from numba import jit
from sklearn.linear_model import LinearRegression
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.stattools import adfuller

logger = logging.getLogger(__name__)


@jit(nopython=True, cache=True)
def _jit_calculate_hurst_exponent(x: np.ndarray) -> float:
    """
    JIT-compiled core for Hurst Exponent calculation using Rescaled Range (R/S) analysis.
    """
    n_total = len(x)

    # Lags: powers of 2 (8, 16, ..., 512)
    lags = []
    # Powers of 2 from 8 (2^3) to 512 (2^9)
    current_lag = 8
    while current_lag <= 512:
        if current_lag <= n_total // 2:
            lags.append(current_lag)
        current_lag *= 2

    if len(lags) < 2:
        # Fallback to linear lags if series is short
        lags = []
        for val in [10, 15, 20, 25]:
            if val <= n_total // 2:
                lags.append(val)

    if len(lags) < 2:
        return 0.5

    valid_lags_log = []
    valid_rs_log = []

    for l in lags:
        n_segments = n_total // l
        if n_segments < 1:
            continue

        sum_rs = 0.0
        count_rs = 0

        for i in range(n_segments):
            # Segment: x[i*l : (i+1)*l]
            start = i * l
            end = start + l

            # Calculate mean
            s_sum = 0.0
            for k in range(start, end):
                s_sum += x[k]
            mean = s_sum / l

            # Calculate range and std
            current_z = 0.0
            min_z = 0.0
            max_z = 0.0
            sum_sq_diff = 0.0

            for k in range(start, end):
                diff = x[k] - mean
                current_z += diff
                if current_z > max_z:
                    max_z = current_z
                if current_z < min_z:
                    min_z = current_z

                sum_sq_diff += diff * diff

            r_val = max_z - min_z
            # Population std (ddof=0)
            std_val = np.sqrt(sum_sq_diff / l)

            if std_val > 1e-12:
                rs = r_val / std_val
                if rs > 0:
                    sum_rs += rs
                    count_rs += 1

        if count_rs > 0:
            avg_rs = sum_rs / count_rs
            valid_lags_log.append(np.log(float(l)))
            valid_rs_log.append(np.log(avg_rs))

    n_valid = len(valid_lags_log)
    if n_valid < 2:
        return 0.5

    # Linear regression: slope of log(R/S) vs log(n)
    sum_x = 0.0
    sum_y = 0.0
    sum_xy = 0.0
    sum_xx = 0.0

    for i in range(n_valid):
        vx = valid_lags_log[i]
        vy = valid_rs_log[i]
        sum_x += vx
        sum_y += vy
        sum_xy += vx * vy
        sum_xx += vx * vx

    denom = n_valid * sum_xx - sum_x * sum_x
    if abs(denom) < 1e-12:
        return 0.5

    slope = (n_valid * sum_xy - sum_x * sum_y) / denom

    if slope < 0.0:
        return 0.0
    if slope > 1.0:
        return 1.0
    return slope


def calculate_hurst_exponent(x: np.ndarray) -> Optional[float]:
    """
    Calculates the Hurst Exponent using Rescaled Range (R/S) analysis.
    Values:
    - H > 0.5: Trending (Persistent)
    - H < 0.5: Mean-reverting (Anti-persistent)
    - H = 0.5: Random Walk (Brownian Motion)
    Returns None if history < 32 sessions.
    """
    # Clean NaNs
    x = x[~np.isnan(x)]
    if len(x) < 32:
        return None

    try:
        return _jit_calculate_hurst_exponent(x)
    except Exception as e:
        logger.debug(f"Hurst calculation failed: {e}")
        return 0.5


@jit(nopython=True, cache=True)
def _jit_calculate_perm_entropy_raw(x: np.ndarray, order: int, delay: int) -> float:
    n_samples = len(x)
    n = n_samples - (order - 1) * delay

    if n <= 0:
        return 0.0

    # Encode permutations
    # Since we can't use complex hash maps, and order is small,
    # we'll map rank tuples to integers.
    encoded = np.empty(n, dtype=np.int64)

    # Pre-allocate arrays for loop
    segment = np.empty(order, dtype=x.dtype)

    for i in range(n):
        # Extract segment
        for k in range(order):
            segment[k] = x[i + k * delay]

        # Argsort to get ranks
        p = np.argsort(segment)

        # Encode rank tuple to integer
        # treated as base-order digits
        code = 0
        factor = 1
        for k in range(order):
            code += p[k] * factor
            factor *= order

        encoded[i] = code

    # Count unique elements
    encoded.sort()

    shannon_entropy = 0.0

    current_code = encoded[0]
    count = 1

    for i in range(1, n):
        if encoded[i] == current_code:
            count += 1
        else:
            prob = count / n
            shannon_entropy -= prob * np.log(prob)
            current_code = encoded[i]
            count = 1

    # Process last group
    prob = count / n
    shannon_entropy -= prob * np.log(prob)

    return shannon_entropy


def calculate_permutation_entropy(x: np.ndarray, order: int = 3, delay: int = 1) -> Optional[float]:
    """
    Calculates Permutation Entropy as a measure of structural randomness.
    Low values = ordered/trending, High values = noisy/random.
    Returns None if history < order.
    """
    x = x[~np.isnan(x)]
    if len(x) < order:
        return None

    try:
        pe_val = _jit_calculate_perm_entropy_raw(x, order, delay)
        # Normalize by log(n!) which is the maximum possible entropy for order n
        return float(pe_val / math.log(math.factorial(order)))
    except Exception:
        return 0.0


def calculate_efficiency_ratio(returns: np.ndarray) -> Optional[float]:
    """
    Calculates Kaufman's Efficiency Ratio (ER).
    ER = |Total Change| / Sum of Absolute Changes

    Higher ER (approaching 1.0) indicates a more efficient trend.
    Lower ER (approaching 0.0) indicates high noise/chop.
    Returns None if history < 10 sessions.
    """
    # Clean NaNs
    returns = returns[~np.isnan(returns)]
    if len(returns) < 10:
        return None

    # Net cumulative return
    net_change = abs(np.sum(returns))

    # Total path length (sum of absolute returns)
    path_length = np.sum(np.abs(returns))

    if path_length <= 1e-12:
        return 0.0

    return float(net_change / path_length)


def calculate_dwt_turbulence(returns: np.ndarray) -> Optional[float]:
    """
    Uses Discrete Wavelet Transform to measure high-frequency 'turbulence'.
    Returns a value in [0, 1] representing the fraction of energy in noise.
    Returns None if history < 8 sessions.
    """
    returns = returns[~np.isnan(returns)]
    if len(returns) < 8:
        return None

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


def calculate_stationarity_score(returns: np.ndarray) -> Optional[float]:
    """
    Uses Augmented Dickey-Fuller (ADF) test to measure stationarity.
    Returns a score in [0, 1] where 1.0 is highly non-stationary/trending.
    Returns None if history < 20 sessions.
    """
    if len(returns) < 20:
        return None

    try:
        if len(returns) < 2 or float(np.nanstd(returns)) < 1e-12:
            return 0.5

        # p-value: probability that the process has a unit root (non-stationary)
        # StatsModels ADF can emit RuntimeWarnings for degenerate series; suppress locally.
        with np.errstate(divide="ignore", invalid="ignore"):
            result = adfuller(returns)
        p_value = float(result[1])
        return p_value  # High p-value = non-stationary
    except Exception as e:
        logger.debug(f"ADF test failed: {e}")
        return 0.5


def calculate_autocorrelation(x: np.ndarray, lag: int = 1) -> float:
    """
    Calculates serial correlation at a specific lag.
    High absolute values indicate self-predictability (trend or mean-reversion).
    """
    x = x[~np.isnan(x)]
    if len(x) <= lag:
        return 0.0
    try:
        corr = np.corrcoef(x[:-lag], x[lag:])[0, 1]
        return float(np.nan_to_num(corr, nan=0.0))
    except Exception:
        return 0.0


def calculate_correlation_structure(x: np.ndarray, max_lags: int = 5) -> Dict[int, float]:
    """
    Returns a dictionary of autocorrelation values for multiple lags.
    """
    return {lag: calculate_autocorrelation(x, lag=lag) for lag in range(1, max_lags + 1)}


def calculate_memory_depth(x: np.ndarray, threshold: float = 0.02) -> int:
    """
    Calculates how many consecutive lags have an autocorrelation above the threshold.
    Indicates the 'memory' of a trend.
    """
    depth = 0
    for lag in range(1, 21):
        ac = calculate_autocorrelation(x, lag=lag)
        if ac > threshold:
            depth += 1
        else:
            break
    return depth


def calculate_half_life(series: np.ndarray) -> float:
    """
    Calculates the Mean Reversion Half-Life using the Ornstein-Uhlenbeck process.
    Models Δp = alpha + beta * p_{t-1} + epsilon.
    Half-life = -ln(2) / beta.

    Returns:
        float: Expected bars to revert half-way. np.inf if not reverting.
    """
    series = series[~np.isnan(series)]
    if len(series) < 30:
        return np.inf

    try:
        # Lagged series
        y = np.diff(series)
        x = series[:-1]

        model = LinearRegression().fit(x.reshape(-1, 1), y)
        beta = float(model.coef_[0])

        if beta >= 0:
            return np.inf  # Not mean-reverting

        half_life = -np.log(2) / beta
        return float(np.clip(half_life, 0.5, 500.0))
    except Exception:
        return np.inf


def calculate_trend_duration(series: np.ndarray, window: int = 50) -> int:
    """
    Calculates the current trend duration (age) based on price position vs EMA.
    Returns the number of consecutive bars the current state has held.
    """
    series = series[~np.isnan(series)]
    if len(series) < window + 10:
        return 0

    try:
        import pandas as pd

        s = pd.Series(series)
        ema = s.ewm(span=window, adjust=False).mean()

        # Above/Below state
        state = (s > ema).astype(int)
        current_state = state.iloc[-1]

        # Count backwards
        count = 0
        for i in range(len(state) - 1, -1, -1):
            if state.iloc[i] == current_state:
                count += 1
            else:
                break
        return count
    except Exception:
        return 0


def calculate_ljungbox_pvalue(x: np.ndarray, lags: int = 5) -> Optional[float]:
    """
    Performs Ljung-Box Q-test for serial correlation.
    Returns the minimum p-value across specified lags.
    Small p-values (< 0.05) indicate significant self-predictability (not white noise).
    Returns None if history < lags + 1.
    """
    x = x[~np.isnan(x)]
    if len(x) < lags + 1:
        return None
    try:
        # lb_stat, p_value
        res = acorr_ljungbox(x, lags=lags, return_df=True)
        return float(res["lb_pvalue"].min())
    except Exception as e:
        logger.debug(f"Ljung-Box test failed: {e}")
        return 1.0
