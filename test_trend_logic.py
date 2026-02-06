import numpy as np
import pandas as pd
import time


def trend_logic_current(s_rets, window=20):
    ma_rets = s_rets.rolling(window=window).mean()
    vals = ma_rets.values
    shifted = np.roll(vals, 1)
    shifted[0] = -1.0
    sig_vals = (shifted > 0).astype(float)
    return s_rets * pd.Series(sig_vals, index=s_rets.index)


def trend_logic_pandas(s_rets, window=20):
    ma_rets = s_rets.rolling(window=window).mean()
    sig_vals = (ma_rets.shift(1).fillna(-1.0) > 0).astype(float)
    return s_rets * sig_vals


# Test correctness
s_rets = pd.Series([0.01, 0.02, -0.01, 0.03, -0.02, 0.01, 0.04, -0.01])
window = 3

res_current = trend_logic_current(s_rets, window)
res_pandas = trend_logic_pandas(s_rets, window)

print("Current result:")
print(res_current)
print("\nPandas result:")
print(res_pandas)

pd.testing.assert_series_equal(res_current, res_pandas)
print("\nAssertion passed: Results are identical.")

# Test performance
large_rets = pd.Series(np.random.normal(0, 0.01, 1000000))

start = time.time()
for _ in range(10):
    trend_logic_current(large_rets, window=252)
end = time.time()
print(f"\nCurrent (np.roll) time: {end - start:.4f}s")

start = time.time()
for _ in range(10):
    trend_logic_pandas(large_rets, window=252)
end = time.time()
print(f"\nPandas (shift) time: {end - start:.4f}s")
