import json
from pathlib import Path


def audit_run(run_id: str):
    audit_path = Path(f"artifacts/summaries/runs/{run_id}/audit.jsonl")
    if not audit_path.exists():
        print(f"Run {run_id} not found.")
        return

    print(f"\n--- Forensic Audit: {run_id} ---")

    anomalies = []
    solver_failures = 0
    sparse_pools = 0

    with open(audit_path, "r") as f:
        for line in f:
            try:
                entry = json.loads(line)
                if entry.get("type") == "action" and entry.get("step") == "backtest_optimize":
                    if entry.get("status") == "error":
                        solver_failures += 1
                        continue

                    outcome = entry.get("outcome", {})
                    metrics = outcome.get("metrics", {})
                    context = entry.get("context", {})

                    sharpe = metrics.get("sharpe", 0)
                    ann_ret = metrics.get("ann_ret", 0)

                    # Outlier detection
                    if sharpe > 10 or sharpe < -5:
                        anomalies.append({"window": context.get("window_index"), "profile": context.get("actual_profile"), "metric": "Sharpe", "value": sharpe})

                    if ann_ret > 10 or ann_ret < -0.9:
                        anomalies.append({"window": context.get("window_index"), "profile": context.get("actual_profile"), "metric": "AnnRet", "value": ann_ret})

                if entry.get("type") == "action" and entry.get("step") == "natural_selection":
                    outcome = entry.get("outcome", {})
                    n_winners = outcome.get("n_winners", 0)
                    if n_winners < 3:
                        sparse_pools += 1

            except Exception as e:
                continue

    print(f"Total Solver Failures: {solver_failures}")
    print(f"Sparse Winner Pools (n < 3): {sparse_pools}")
    if anomalies:
        print(f"Detected {len(anomalies)} anomalies:")
        for a in anomalies[:10]:  # Top 10
            print(f"  - Window {a['window']} ({a['profile']}): {a['metric']} = {a['value']:.2f}")
        if len(anomalies) > 10:
            print(f"  ... and {len(anomalies) - 10} more.")
    else:
        print("No extreme metric anomalies detected.")


if __name__ == "__main__":
    runs = ["20260118-161253", "20260118-161504", "20260118-161655", "20260118-161849"]
    for run in runs:
        audit_run(run)
