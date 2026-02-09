import vectorbt as vbt
import pandas as pd
import numpy as np


def test_vbt_sl():
    print("Testing VectorBT SL with from_signals...")

    # 1. Setup Data
    # Price: 100 -> 90 (Drop 10%) -> 110 (Recovery)
    prices = pd.Series([100.0, 90.0, 110.0], name="BTC")

    # Weights: Enter 1.0 at t=0, Hold at t=1, t=2
    # In Signal mode, we signal Entry at t=0.
    entries = pd.Series([True, False, False], name="BTC", index=prices.index)
    exits = pd.Series([False, False, False], name="BTC", index=prices.index)  # SL will trigger exit

    # SL = 0.05 (5%).
    # At t=1, Price 90. Drop is 10%. SL should trigger.

    try:
        pf = vbt.Portfolio.from_signals(close=prices, entries=entries, exits=exits, sl_stop=0.05, freq="1d", init_cash=10000, fees=0.0)

        print("Portfolio executed.")
        # Records readable is safer than accessing arrays directly for logging
        print(pf.orders.records_readable)

        # Check if Exit triggered
        orders = pf.orders.records_readable
        if len(orders) > 1:
            print("Orders found:", len(orders))
            print("SUCCESS: SL triggered an exit.")
        else:
            print("FAILURE: No exit order found.")

    except Exception as e:
        print(f"CRASH: {e}")


if __name__ == "__main__":
    test_vbt_sl()
