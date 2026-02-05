import json
import numpy as np
import pandas as pd

try:
    data = {"int_val": np.int64(42), "float_val": np.float64(3.14), "pd_ts": pd.Timestamp("2023-01-01")}

    def default(o):
        if isinstance(o, (pd.Timestamp, pd.Period)):
            return str(o)
        return str(o)  # This effectively casts everything else to string, including numpy types!

    # Wait, the current implementation is:
    # def default(o):
    #     if isinstance(o, (pd.Timestamp, pd.Period)):
    #         return str(o)
    #     return str(o)

    # If the default handler is called, it means it's not a basic type.
    # The default handler above returns str(o) for EVERYTHING it catches.
    # So np.int64(42) -> "42".
    # This might be valid JSON (string "42"), but it changes the type from number to string.

    print(json.dumps(data, default=default))
except Exception as e:
    print(f"Error: {e}")
