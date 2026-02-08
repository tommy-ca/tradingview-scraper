import logging
import sys
from pathlib import Path

sys.path.append(".")
from scripts.build_meta_returns import build_meta_returns

logging.basicConfig(level=logging.DEBUG)

print("Starting debug build_meta_returns...")
try:
    df = build_meta_returns(meta_profile="meta_benchmark", output_path="debug_meta.pkl", profiles=["hrp"], manifest_path=Path("configs/manifest.json"))
    if isinstance(df, tuple):
        # It might return (df, something) in some versions? No, expected df.
        pass

    # Check if df is None
    if df is None:
        print("Result is None")
    else:
        print("Result shape:", df.shape)
        print("Columns:", df.columns)
except Exception as e:
    import traceback

    traceback.print_exc()
    print(f"Error: {e}")
