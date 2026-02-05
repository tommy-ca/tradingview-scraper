import json
import numpy as np
import pandas as pd


def default(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, (pd.Timestamp, pd.Period)):
        return str(o)
    return str(o)


data = {"int": np.int64(42), "float": np.float64(3.14), "bool": np.bool_(True), "array": np.array([1, 2, 3]), "timestamp": pd.Timestamp("2023-01-01")}

try:
    print(json.dumps(data, default=default, indent=2))
except Exception as e:
    print(f"Error: {e}")
