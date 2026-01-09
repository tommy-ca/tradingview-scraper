import json
import sys

import pandas as pd

log_path = "artifacts/summaries/runs/20260109-175648/audit.jsonl"
data = []

with open(log_path, "r") as f:
    for line in f:
        try:
            entry = json.loads(line)
            if entry.get("step") == "backtest_simulate" and entry.get("status") == "success":
                ctx = entry.get("context", {})
                outcome = entry.get("outcome", {}).get("metrics", {})

                data.append({"window": ctx.get("window_index"), "profile": ctx.get("profile"), "engine": ctx.get("engine"), "sharpe": outcome.get("sharpe")})
        except Exception:
            continue

df = pd.DataFrame(data)
if df.empty:
    print("No backtest data found")
    sys.exit(0)

# Pivot to see Profile vs Window
pivot = df.pivot_table(index="window", columns=["engine", "profile"], values="sharpe", aggfunc="mean")
print(pivot.to_markdown())
