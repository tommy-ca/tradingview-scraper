import logging
import os

import numpy as np
import pandas as pd
import ray

from scripts.backtest_engine import BacktestEngine

logging.basicConfig(level=logging.INFO)


def validate_ray():
    print("Checking Ray integration...")
    if not ray.is_initialized():
        ray.init()

    # Create dummy data
    dates = pd.date_range("2023-01-01", periods=100)
    data = pd.DataFrame(
        np.random.randn(100, 5) / 100,
        index=dates,
        columns=pd.Index([f"S{i}" for i in range(5)]),
    )

    # Save dummy data
    path = "data/lakehouse/test_returns.pkl"
    os.makedirs("data/lakehouse", exist_ok=True)
    data.to_pickle(path)

    os.environ["TV_USE_RAY"] = "1"
    os.environ["TV_RETURNS_PATH"] = path

    engine = BacktestEngine(returns_path=path)

    print("Running tournament with Ray...")
    res = engine.run_tournament(profiles=["hrp"], engines=["custom"], simulators=["custom"], train_window=30, test_window=10, step_size=30)

    print(f"Tournament completed. Windows: {res['meta']['n_windows']}")
    print("Ray integration validated successfully.")


if __name__ == "__main__":
    validate_ray()
