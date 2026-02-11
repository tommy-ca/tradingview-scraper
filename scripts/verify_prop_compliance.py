import json
import argparse
from pathlib import Path
import pandas as pd


def verify_compliance(audit_path: Path):
    if not audit_path.exists():
        print(f"Error: Audit file not found at {audit_path}")
        return

    print(f"Auditing Prop-Firm Compliance for: {audit_path.parent.name}")

    breaches = []
    with open(audit_path, "r") as f:
        for line in f:
            try:
                event = json.loads(line)
                if event.get("trigger") in ["MAX_DAILY_DRAWDOWN", "GLOBAL_EQUITY_GUARD"]:
                    breaches.append(event)
            except json.JSONDecodeError:
                continue

    if not breaches:
        print("✓ No Risk Breaches detected in this run.")
    else:
        print(f"✗ FOUND {len(breaches)} RISK BREACHES:")
        for b in breaches:
            print(f"  - [{b.get('timestamp')}] {b.get('trigger')} hit! Action: {b.get('action')}")
            print(f"    Details: {b.get('metadata')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", help="Run ID to audit")
    args = parser.parse_args()

    # Path logic (consistent with settings.py)
    audit_file = Path("data/artifacts/summaries/runs") / args.run_id / "audit.jsonl"
    verify_compliance(audit_file)
