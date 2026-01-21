import argparse
import json
import logging
import sys

from tradingview_scraper.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("health_guardrail")


def validate_sleeve_health(run_id: str, threshold: float = 0.75):
    settings = get_settings()
    run_path = settings.summaries_runs_dir / run_id
    audit_path = run_path / "audit.jsonl"

    if not audit_path.exists():
        logger.error(f"❌ Audit ledger missing for run {run_id}: {audit_path}")
        return False

    total_optimizations = 0
    successful_optimizations = 0

    with open(audit_path, "r") as f:
        for line in f:
            try:
                entry = json.loads(line)
                if entry.get("type") == "action" and entry.get("step") == "backtest_optimize":
                    if entry.get("status") == "intent":
                        continue
                    total_optimizations += 1
                    if entry.get("status") == "success":
                        successful_optimizations += 1
            except Exception:
                continue

    if total_optimizations == 0:
        logger.warning(f"⚠️ No optimizations found in audit ledger for run {run_id}.")
        return True  # Or False depending on strictness

    health_ratio = successful_optimizations / total_optimizations
    is_healthy = health_ratio >= threshold

    status_icon = "✅" if is_healthy else "❌"
    logger.info(f"{status_icon} Run {run_id} Solver Health: {health_ratio:.1%} ({successful_optimizations}/{total_optimizations})")

    if not is_healthy:
        logger.error(f"FATAL: Solver health {health_ratio:.1%} is below threshold {threshold:.1%}")

    return is_healthy


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--threshold", type=float, default=0.75)
    args = parser.parse_args()

    if not validate_sleeve_health(args.run_id, args.threshold):
        sys.exit(1)
    sys.exit(0)
