import logging
import math

import numpy as np
import pywt
from numba import float64, int32, int64, njit
from sklearn.linear_model import LinearRegression
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.stattools import adfuller

logger = logging.getLogger(__name__)


@njit(float64(float64[::1]), cache=True, fastmath=True)
def _get_rs_jit(series):
    """
    JIT optimized R/S calculation using scalar tracking (Zero-Allocation).

    Args:
        series: Array of returns or price changes.

    Returns:
        float: The calculated R/S value.

    Audit:
        - Memory: O(1) workspace.
        - Performance: Linear O(n) scan.
    """
    n = len(series)
    if n < 2:
        return 0.0

    m = 0.0
    for i in range(n):
        m += series[i]
    m /= n

    curr = 0.0
    mx = -1e15
    mn = 1e15
    for i in range(n):
        curr += series[i] - m
        if curr > mx:
            mx = curr
        if curr < mn:
            mn = curr

    r = mx - mn

    # Standard deviation
    var = 0.0
    for i in range(n):
        var += (series[i] - m) ** 2
    s = np.sqrt(var / n)

    return r / s if s > 1e-12 else 0.0


def calculate_hurst_exponent(x: np.ndarray) -> float | None:
    """
    Calculates the Hurst Exponent using Rescaled Range (R/S) analysis.
    Values:
    - H > 0.5: Trending (Persistent)
    - H < 0.5: Mean-reverting (Anti-persistent)
    - H = 0.5: Random Walk (Brownian Motion)

    Args:
        x: Input time-series data.

    Returns:
        float | None: Hurst exponent value or None if insufficient history.

    Audit:
        - Memory: Zero-allocation core.
        - Performance: Logarithmic lags traversal.
    """
    x = np.ascontiguousarray(x[~np.isnan(x)], dtype=np.float64)
    if len(x) < 32:
        return None

    try:
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
            n_segments = max(1, n_total // l)
            rs_avg = []
            for i in range(n_segments):
                segment = x[i * l : (i + 1) * l]
                if len(segment) > 0:
                    rs = _get_rs_jit(segment)
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


@njit(float64(float64[::1], int32[::1], float64[::1], int64, int64), cache=True, fastmath=True)
def _calculate_permutation_entropy_jit(x, perm_counts, segment_buffer, order=3, delay=1):
    """
    JIT optimized Permutation Entropy core logic using pre-allocated buffers.

    Args:
        x: Input contiguous float64 array.
        perm_counts: Workspace buffer for permutation frequencies.
        segment_buffer: Workspace buffer for current window segment.
        order: Permutation order (embedding dimension).
        delay: Time delay factor.

    Returns:
        float: Raw entropy value.

    Audit:
        - Memory: Reuses provided buffers.
        - Numerical: Linear O(n) pass.
    """
    n = len(x) - (order - 1) * delay
    num_permutations = n

    # Reset counts buffer
    perm_counts.fill(0)

    for i in range(n):
        # Fill segment from pre-allocated buffer
        for j in range(order):
            segment_buffer[j] = x[i + j * delay]

        perm_idx = np.argsort(segment_buffer)

        key = 0
        for val in perm_idx:
            key = key * order + val

        # Simple safety check for key bounds if needed
        if key < len(perm_counts):
            perm_counts[key] += 1

    # Calculate entropy
    ent = 0.0
    for i in range(len(perm_counts)):
        count = perm_counts[i]
        if count > 0:
            p = count / num_permutations
            ent -= p * np.log(p)

    return ent


def calculate_permutation_entropy(x: np.ndarray, order: int = 3, delay: int = 1) -> float | None:
    """
    Calculates Permutation Entropy as a measure of structural randomness.
    Low values = ordered/trending, High values = noisy/random.

    Args:
        x: Input time-series data.
        order: Embedding dimension (default=3).
        delay: Time delay factor (default=1).

    Returns:
        float | None: Normalized entropy in [0, 1] or None if insufficient history.

    Audit:
        - Memory: Single allocation per call for workspace.
        - Performance: JIT-hardened inner loop.
    """
    x = np.ascontiguousarray(x[~np.isnan(x)], dtype=np.float64)
    if len(x) < order:
        return None

    try:
        # Pre-allocate buffers for JIT
        max_key = int(order**order)
        # Adjust 4000 to be dynamic or at least safe for order 5
        buf_size = max(4000, max_key + 1)
        perm_counts = np.zeros(buf_size, dtype=np.int32)
        segment_buffer = np.zeros(order, dtype=np.float64)

        pe_val = _calculate_permutation_entropy_jit(x, perm_counts, segment_buffer, int(order), int(delay))
        # Normalize by log(n!) which is the maximum possible entropy for order n
        return float(pe_val / math.log(math.factorial(order)))
    except Exception:
        return None


def calculate_efficiency_ratio(returns: np.ndarray) -> float | None:
    """
    Calculates Kaufman's Efficiency Ratio (ER).
    ER = |Total Change| / Sum of Absolute Changes

    Higher ER (approaching 1.0) indicates a more efficient trend.
    Lower ER (approaching 0.0) indicates high noise/chop.

    Args:
        returns: Input return series.

    Returns:
        float | None: Efficiency ratio or None if insufficient history.

    Audit:
        - Memory: NumPy vectorized pass.
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


def calculate_dwt_turbulence(returns: np.ndarray) -> float | None:
    """
    Uses Discrete Wavelet Transform to measure high-frequency 'turbulence'.
    Returns a value in [0, 1] representing the fraction of energy in noise.

    Args:
        returns: Input return series.

    Returns:
        float | None: Turbulence score or None if insufficient history.

    Audit:
        - Technology: PyWavelets Haar decomposition.
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


def calculate_stationarity_score(returns: np.ndarray) -> float | None:
    """
    Uses Augmented Dickey-Fuller (ADF) test to measure stationarity.
    Returns a score in [0, 1] where 1.0 is highly non-stationary/trending.

    Args:
        returns: Input return series.

    Returns:
        float | None: Stationarity p-value or None if insufficient history.

    Audit:
        - Stability: Suppresses divide-by-zero warnings in degenerate cases.
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

    Args:
        x: Input array.
        lag: Correlation lag.

    Returns:
        float: Correlation coefficient.
    """
    x = x[~np.isnan(x)]
    if len(x) <= lag:
        return 0.0
    try:
        corr = np.corrcoef(x[:-lag], x[lag:])[0, 1]
        return float(np.nan_to_num(corr, nan=0.0))
    except Exception:
        return 0.0


def calculate_correlation_structure(x: np.ndarray, max_lags: int = 5) -> dict[int, float]:
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

    Args:
        series: Input price/return series.

    Returns:
        float: Expected bars to revert half-way. np.inf if not reverting.

    Audit:
        - Technology: Scikit-learn LinearRegression.
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

    Args:
        series: Input price/return series.
        window: EMA window size.

    Returns:
        int: Duration count.
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


def calculate_ljungbox_pvalue(x: np.ndarray, lags: int = 5) -> float | None:
    """
    Performs Ljung-Box Q-test for serial correlation.
    Returns the minimum p-value across specified lags.
    Small p-values (< 0.05) indicate significant self-predictability (not white noise).

    Args:
        x: Input array.
        lags: Number of lags to test.

    Returns:
        float | None: Minimum p-value or None if insufficient history.

    Audit:
        - Technology: Statsmodels LB-Q test.
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
