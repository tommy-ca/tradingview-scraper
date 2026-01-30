import json
import logging
from typing import List, Optional, Set

from tradingview_scraper.settings import get_settings

logger = logging.getLogger("health_guardrail")


def validate_sleeve_health(
    run_id: str,
    threshold: float = 0.75,
    engines: Optional[List[str]] = None,
    profiles: Optional[List[str]] = None,
) -> bool:
    settings = get_settings()
    run_path = settings.summaries_runs_dir / run_id
    audit_path = run_path / "audit.jsonl"

    if not audit_path.exists():
        logger.error(f"❌ Audit ledger missing for run {run_id}: {audit_path}")
        return False

    engine_allow: Set[str] = set(e.lower() for e in (engines or ["custom"]))
    profile_allow: Optional[Set[str]] = set(p for p in profiles) if profiles else None

    total_optimizations = 0
    successful_optimizations = 0

    with open(audit_path, "r") as f:
        for line in f:
            try:
                entry = json.loads(line)
                if entry.get("type") == "action" and entry.get("step") == "backtest_optimize":
                    if entry.get("status") == "intent":
                        continue

                    ctx = entry.get("context") or {}
                    engine = str(ctx.get("engine", "")).lower()
                    prof = str(ctx.get("profile", "")).strip()

                    # Meta-layer health should only veto based on the streams it will actually consume.
                    # Default allowlist is "custom" because build_meta_returns prefers `custom_*` return series.
                    if engine_allow and engine not in engine_allow:
                        continue
                    if profile_allow is not None and prof not in profile_allow:
                        continue

                    total_optimizations += 1
                    if entry.get("status") == "success":
                        successful_optimizations += 1
            except Exception:
                continue

    if total_optimizations == 0:
        logger.warning(f"⚠️ No optimizations found in audit ledger for run {run_id} (engines={sorted(engine_allow)} profiles={sorted(profile_allow) if profile_allow else 'ALL'}).")
        return True  # Or False depending on strictness

    health_ratio = successful_optimizations / total_optimizations
    is_healthy = health_ratio >= threshold

    status_icon = "✅" if is_healthy else "❌"
    logger.info(f"{status_icon} Run {run_id} Solver Health: {health_ratio:.1%} ({successful_optimizations}/{total_optimizations}) [engines={sorted(engine_allow)}]")

    if not is_healthy:
        logger.error(f"FATAL: Solver health {health_ratio:.1%} is below threshold {threshold:.1%}")

    return is_healthy
