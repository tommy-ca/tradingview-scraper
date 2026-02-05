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

data = {
    "int64": np.int64(42),
    "float64": np.float64(3.14159),
    "str": "test"
}

try:
    json_str = json.dumps(data, default=default)
    print(f"JSON Output: {json_str}")
    if '"int64": 42' in json_str and '"float64": 3.14159' in json_str:
        print("SUCCESS: Numpy types correctly serialized")
    else:
        print("FAILURE: Serialization incorrect")
        exit(1)
except Exception as e:
    print(f"ERROR: {e}")
    exit(1)
