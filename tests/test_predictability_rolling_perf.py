import math
import time

import numpy as np
import pandas as pd

from tradingview_scraper.utils.predictability import calculate_permutation_entropy, rolling_permutation_entropy


def _slow_rolling_entropy_pandas(x: np.ndarray, *, window: int, order: int = 3) -> np.ndarray:
    s = pd.Series(x)

    # Reuse buffers to avoid measuring allocation overhead.
    max_key = int(order**order)
    perm_counts = np.zeros(max(4000, max_key + 1), dtype=np.int32)
    segment_buffer = np.zeros(int(order), dtype=np.float64)

    def f(arr: np.ndarray) -> float:
        v = calculate_permutation_entropy(arr, order=order, delay=1, perm_counts=perm_counts, segment_buffer=segment_buffer)
        return np.nan if v is None else float(v)

    return s.rolling(int(window)).apply(f, raw=True).to_numpy(dtype=np.float64)


def _permutation_entropy_python(arr: np.ndarray, *, order: int = 3, delay: int = 1) -> float:
    x = np.asarray(arr, dtype=np.float64)
    n = len(x) - (order - 1) * delay
    if n <= 0:
        return np.nan

    counts: dict[tuple[int, ...], int] = {}
    valid = 0
    for i in range(n):
        seg = x[i : i + order * delay : delay]
        if np.isnan(seg).any():
            continue
        perm = tuple(int(p) for p in np.argsort(seg))
        counts[perm] = counts.get(perm, 0) + 1
        valid += 1

    if valid == 0:
        return np.nan

    ent = 0.0
    for c in counts.values():
        p = c / valid
        ent -= p * math.log(p)

    denom = math.log(math.factorial(order))
    return float(ent / denom) if denom > 0 else float(ent)


def _slow_rolling_entropy_pandas_python(x: np.ndarray, *, window: int, order: int = 3) -> np.ndarray:
    s = pd.Series(x)

    def f(arr: np.ndarray) -> float:
        return _permutation_entropy_python(arr, order=order, delay=1)

    return s.rolling(int(window)).apply(f, raw=True).to_numpy(dtype=np.float64)


def test_rolling_permutation_entropy_matches_pandas_apply():
    rng = np.random.default_rng(1337)
    x = rng.normal(0.0, 0.01, size=600).astype(np.float64)
    x[0] = np.nan  # realistic pct_change() style leading NaN

    window = 50
    order = 3
    fast = rolling_permutation_entropy(x, window=window, order=order, delay=1)
    slow = _slow_rolling_entropy_pandas(x, window=window, order=order)

    mask = ~np.isnan(fast) & ~np.isnan(slow)
    assert mask.sum() > 0
    np.testing.assert_allclose(fast[mask], slow[mask], rtol=1e-9, atol=1e-12)


def test_rolling_permutation_entropy_is_meaningfully_faster_than_pandas_apply():
    rng = np.random.default_rng(7)
    x = rng.normal(0.0, 0.01, size=220).astype(np.float64)
    x[0] = np.nan
    window = 40
    order = 3

    # Warm-up JIT compilation (exclude from timing).
    rolling_permutation_entropy(x[:120], window=30, order=order, delay=1)
    _slow_rolling_entropy_pandas_python(x[:120], window=30, order=order)

    t0 = time.perf_counter()
    fast = rolling_permutation_entropy(x, window=window, order=order, delay=1)
    t_fast = time.perf_counter() - t0

    t0 = time.perf_counter()
    slow = _slow_rolling_entropy_pandas_python(x, window=window, order=order)
    t_slow = time.perf_counter() - t0

    # Basic sanity: output shapes match.
    assert fast.shape == slow.shape

    # Guardrail: avoid regressions back to python-level rolling apply.
    # Ratio is intentionally conservative to reduce CI flakiness.
    assert t_fast * 8.0 < t_slow, f"Expected fast rolling entropy to be >=8x faster (fast={t_fast:.4f}s slow={t_slow:.4f}s)"
