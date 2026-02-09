import vectorbt as vbt
import pandas as pd
import numpy as np

try:
    prices = pd.DataFrame({"a": [10, 11, 12, 11, 10]}, index=pd.date_range("2021-01-01", periods=5))
    size = pd.DataFrame({"a": [0.1, 0.1, 0.1, 0.1, 0.1]}, index=prices.index)

    # Try passing sl_stop to from_orders
    try:
        pf = vbt.Portfolio.from_orders(prices, size, size_type="target_percent", sl_stop=0.05)
        print("SUCCESS: from_orders accepts sl_stop")
    except TypeError as e:
        print(f"FAILURE: from_orders does NOT accept sl_stop: {e}")

except Exception as e:
    print(f"ERROR: {e}")
