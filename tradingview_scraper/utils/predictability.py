import logging
import math

import numpy as np
import pywt
from numba import float64, int32, int64, njit
from sklearn.linear_model import LinearRegression
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.stattools import adfuller

logger = logging.getLogger(__name__)


@njit(float64(float64[::1], float64[::1]), cache=True, fastmath=True)
def _get_rs_jit(series, z_buffer):
    """
    JIT optimized R/S calculation using scalar tracking (Zero-Allocation).
    Handles NaNs internally by skipping them.
    z_buffer is provided for API compatibility and future buffer-heavy optimizations.

    Args:
        series: Array of returns or price changes.
        z_buffer: Pre-allocated workspace (currently unused by scalar implementation).

    Returns:
        float: The calculated R/S value.
    """
    # Count valid (non-NaN) observations
    n_valid = 0
    m = 0.0
    for i in range(len(series)):
        val = series[i]
        if not np.isnan(val):
            m += val
            n_valid += 1

    if n_valid < 2:
        return 0.0

    m /= n_valid

    curr = 0.0
    mx = -1e15
    mn = 1e15
    var = 0.0

    for i in range(len(series)):
        val = series[i]
        if not np.isnan(val):
            curr += val - m
            if curr > mx:
                mx = curr
            if curr < mn:
                mn = curr
            var += (val - m) ** 2

    r = mx - mn
    s = np.sqrt(var / n_valid)

    return r / s if s > 1e-12 else 0.0


def calculate_hurst_exponent(x: np.ndarray, z_buffer: np.ndarray | None = None) -> float | None:
    """
    Calculates the Hurst Exponent using Rescaled Range (R/S) analysis.
    Values:
    - H > 0.5: Trending (Persistent)
    - H < 0.5: Mean-reverting (Anti-persistent)
    - H = 0.5: Random Walk (Brownian Motion)

    Args:
        x: Input time-series data.
        z_buffer: Optional pre-allocated workspace buffer.

    Returns:
        float | None: Hurst exponent value or None if insufficient history.
    """
    # Pillar 3: Ensure memory contiguity for JIT efficiency
    x_arr = np.ascontiguousarray(x, dtype=np.float64)
    n_total = len(x_arr)

    # Check total non-NaN observations
    if np.sum(~np.isnan(x_arr)) < 32:
        return None

    try:
        if z_buffer is None:
            z_buffer = np.zeros(n_total, dtype=np.float64)

        # Divide into segments
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
                segment = x_arr[i * l : (i + 1) * l]
                if len(segment) > 0:
                    rs = _get_rs_jit(segment, z_buffer[: len(segment)])
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


@njit(float64[:](float64[::1], int64, int32[::1], float64[::1], int64, int64), cache=True, fastmath=True)
def compute_rolling_entropy_numba(x, window, perm_counts, segment_buffer, order=3, delay=1):
    """
    Optimized rolling permutation entropy using pre-allocated buffers.
    (Pillar 3: Zero-Allocation in hot loop).
    """
    n = len(x)
    out = np.full(n, np.nan)
    if n < window:
        return out

    for i in range(window, n + 1):
        segment = x[i - window : i]
        # We reuse the buffers by passing them to the kernel
        out[i - 1] = _calculate_permutation_entropy_jit(segment, perm_counts, segment_buffer, order, delay)
    return out


@njit(float64[:](float64[::1], int64, float64[::1]), cache=True, fastmath=True)
def compute_rolling_hurst_numba(x, window, z_buffer):
    """
    Optimized rolling R/S analysis using pre-allocated buffers.
    Used as a proxy for Hurst in high-frequency rolling windows.
    """
    n = len(x)
    out = np.full(n, np.nan)
    if n < window:
        return out

    for i in range(window, n + 1):
        segment = x[i - window : i]
        out[i - 1] = _get_rs_jit(segment, z_buffer)
    return out


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
