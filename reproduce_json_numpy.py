import json
import numpy as np
import pandas as pd

data = {"np_int": np.int64(42), "np_float": np.float64(3.14), "pure_int": 42, "pure_float": 3.14}


def default(o):
    return f"STR_{o}"


print("Without default (might crash):")
try:
    print(json.dumps(data))
except TypeError as e:
    print(f"Crash: {e}")

print("\nWith str default:")
print(json.dumps(data, default=default))
