import numpy as np
import pytest

from tradingview_scraper.utils.predictability import calculate_dwt_turbulence, calculate_efficiency_ratio, calculate_hurst_exponent, calculate_permutation_entropy, calculate_stationarity_score


@pytest.fixture
def random_walk():
    np.random.seed(42)
    return np.cumsum(np.random.randn(100))


@pytest.fixture
def trending_series():
    return np.linspace(0, 10, 100) + np.random.randn(100) * 0.1


@pytest.fixture
def noisy_series():
    np.random.seed(42)
    return np.random.randn(100)


@pytest.fixture
def sine_wave():
    return np.sin(np.linspace(0, 10 * np.pi, 100))


def test_hurst_exponent(random_walk, trending_series, noisy_series):
    # Hurst should be calculated on returns (increments)
    h_rw = calculate_hurst_exponent(np.diff(random_walk))
    h_trend = calculate_hurst_exponent(np.diff(trending_series))
    h_noise = calculate_hurst_exponent(noisy_series)

    # Random walk increments (white noise) should be around 0.5
    assert 0.3 <= h_rw <= 0.7
    # Trending increments (positive mean) should still be around 0.5
    # unless the increments themselves are persistent (momentum).
    # Wait, Kaufman's ER is better for trend. Hurst is for memory.
    # Let's adjust expectations: white noise Hurst is 0.5.

    # Actually, a "trending" price series usually has persistent increments if it's a real trend?
    # No, a trend can have zero autocorrelation in returns but a non-zero mean.
    # Hurst > 0.5 means positive autocorrelation in returns.

    # Let's use a persistent series for Hurst > 0.5
    persistent_noise = np.zeros(100)
    for i in range(1, 100):
        persistent_noise[i] = 0.6 * persistent_noise[i - 1] + np.random.randn()

    h_persistent = calculate_hurst_exponent(persistent_noise)
    assert h_persistent > 0.5


def test_permutation_entropy(trending_series, noisy_series, sine_wave):
    pe_trend = calculate_permutation_entropy(trending_series)
    pe_noise = calculate_permutation_entropy(noisy_series)
    pe_sine = calculate_permutation_entropy(sine_wave)

    # Noise should have high entropy (close to 1.0)
    assert pe_noise > 0.8
    # Trending should have lower entropy than noise
    assert pe_trend < pe_noise
    # Structured patterns should have lower entropy
    assert pe_sine < 0.7


def test_efficiency_ratio():
    # Perfect trend
    # Need at least 10 returns, so 11 points
    perfect_trend = np.linspace(100, 200, 11)
    # Returns are [10, 10, ...]
    # ER = |Total Change| / Sum of Absolute Changes = 100 / 100 = 1.0
    er_perfect = calculate_efficiency_ratio(np.diff(perfect_trend))
    assert er_perfect == 1.0

    # Pure noise (choppy)
    choppy = np.array([1, -1] * 6)  # 12 points -> 11 returns
    # Returns are [-2, 2, -2, 2, -2, 2, -2, 2, -2, 2, -2]
    # ER = |-2+2-2+2...-2| / sum(abs) = |-2| / (2*11) = 2/22 = 1/11
    er_choppy = calculate_efficiency_ratio(np.diff(choppy))
    assert er_choppy < 0.1


def test_dwt_turbulence(trending_series, noisy_series):
    turb_trend = calculate_dwt_turbulence(trending_series)
    turb_noise = calculate_dwt_turbulence(noisy_series)

    # Noise should have higher high-frequency energy (turbulence)
    assert turb_noise > turb_trend


def test_stationarity_score(trending_series, noisy_series):
    s_trend = calculate_stationarity_score(trending_series)
    s_noise = calculate_stationarity_score(noisy_series)

    # Trending series is non-stationary (high p-value)
    # Noise is stationary (low p-value)
    assert s_trend > s_noise
