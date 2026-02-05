from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from tradingview_scraper.data.loader import DataLoader
from tradingview_scraper.orchestration.registry import StageRegistry
from tradingview_scraper.settings import get_settings

logger = logging.getLogger(__name__)


def validate_sleeve_health(run_id: str, threshold: float = 0.75, engines: list[str] | None = None, profiles: list[str] | None = None) -> bool:
    """
    Validates the solver health of a specific backtest run.
    Checks audit.jsonl for successful optimizations.
    """
    settings = get_settings()
    run_path = settings.summaries_runs_dir / run_id
    audit_path = run_path / "audit.jsonl"

    if not audit_path.exists():
        logger.error(f"❌ Audit ledger missing for run {run_id}: {audit_path}")
        return False

    engine_allow = set(e.lower() for e in (engines or ["custom"]))
    profile_allow = set(p for p in profiles) if profiles else None

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
        logger.warning(f"⚠️ No optimizations found in audit ledger for run {run_id}.")
        return True

    health_ratio = successful_optimizations / total_optimizations
    is_healthy = health_ratio >= threshold

    status_icon = "✅" if is_healthy else "❌"
    logger.info(f"{status_icon} Run {run_id} Solver Health: {health_ratio:.1%} ({successful_optimizations}/{total_optimizations})")

    return is_healthy


def get_meta_cache_key(meta_profile: str, prof: str, sleeves: list[dict[str, Any]]) -> str:
    """Generate a unique key based on sleeve profiles and run_ids."""
    components = [meta_profile, prof]
    for s in sleeves:
        s_id = s.get("id") or s.get("profile") or "unknown"
        components.append(f"{s_id}:{s.get('run_id', 'dynamic')}")

    return hashlib.sha256("|".join(components).encode()).hexdigest()[:16]


@StageRegistry.register(
    id="meta.aggregation",
    name="Meta Return Aggregation",
    description="Aggregates returns from multiple atomic sleeves into a meta-returns matrix.",
    category="meta",
    tags=["meta", "returns"],
)
def build_meta_returns(
    meta_profile: str,
    output_path: str,
    profiles: list[str] | None = None,
    manifest_path: Path = Path("configs/manifest.json"),
    base_dir: Path | None = None,
    depth: int = 0,
    visited: list[str] | None = None,
) -> bool:
    """
    Aggregates returns from multiple atomic sleeves into a meta-returns matrix.
    Supports fractal recursion and caching.
    """
    settings = get_settings()
    loader = DataLoader(settings)
    work_dir = base_dir or settings.lakehouse_dir

    visited = visited or []
    if meta_profile in visited:
        raise RuntimeError(f"Circular dependency detected: {' -> '.join(visited)} -> {meta_profile}")
    if depth > 3:
        raise RuntimeError(f"Max fractal depth exceeded (depth={depth}) for profile: {meta_profile}")

    current_visited = visited + [meta_profile]

    if not manifest_path.exists():
        logger.error(f"Manifest missing: {manifest_path}")
        return False

    with open(manifest_path, "r") as f:
        full_manifest = json.load(f)

    profile_cfg = full_manifest.get("profiles", {}).get(meta_profile)
    if not profile_cfg:
        logger.error(f"Profile {meta_profile} not found in manifest")
        return False

    sleeves = profile_cfg.get("sleeves", [])
    if not sleeves:
        logger.error(f"No sleeves defined for profile {meta_profile}")
        return False

    target_profiles = profiles or settings.profiles.split(",")

    for prof in target_profiles:
        prof = prof.strip()
        cache_key = get_meta_cache_key(meta_profile, prof, sleeves)
        cache_dir = settings.lakehouse_dir / ".cache"
        # Transition to Parquet for cache
        cache_file = cache_dir / f"{meta_profile}_{prof}_{cache_key}.parquet"
        manifest_cache = cache_dir / f"{meta_profile}_{prof}_{cache_key}_manifest.json"

        if cache_file.exists() and manifest_cache.exists():
            logger.info(f"  [CACHE HIT] {meta_profile}/{prof} (Key: {cache_key})")
            continue

        meta_df = pd.DataFrame()
        sleeve_metadata = []

        for sleeve in sleeves:
            s_id = sleeve["id"]

            if "meta_profile" in sleeve:
                sub_meta = sleeve["meta_profile"]
                sub_returns_file = work_dir / f"meta_returns_{sub_meta}_{prof}.parquet"
                build_meta_returns(sub_meta, str(sub_returns_file), [prof], manifest_path, base_dir=work_dir, depth=depth + 1, visited=current_visited)

                if not sub_returns_file.exists():
                    continue

                s_rets_raw = pd.read_parquet(sub_returns_file)
                # Simplified: use mean for nested if not optimized (logic moved from script)
                s_rets = s_rets_raw.mean(axis=1).to_frame(s_id)
                target_file = sub_returns_file
            else:
                s_profile = sleeve["profile"]
                run_path = loader.find_latest_run_for_profile(s_profile)

                if not run_path or not validate_sleeve_health(run_path.name, threshold=0.75, engines=["custom"]):
                    continue

                returns_dir = run_path / "data" / "returns"
                # Preference: Parquet Only
                target_file = next(returns_dir.glob(f"*_{prof}.parquet"), None)

                if not target_file:
                    continue

                s_rets_raw = pd.read_parquet(target_file)

                s_rets = s_rets_raw.iloc[:, 0].to_frame(s_id) if isinstance(s_rets_raw, pd.DataFrame) else s_rets_raw.to_frame(s_id)

            # Alignment
            s_rets.index = pd.to_datetime(s_rets.index).tz_localize(None)
            meta_df = s_rets if meta_df.empty else meta_df.join(s_rets, how="inner")

        if not meta_df.empty:
            out_p = Path(output_path).parent / f"meta_returns_{meta_profile}_{prof}.parquet"
            meta_df.to_parquet(out_p)
            logger.info(f"✅ Meta-Returns ({meta_profile}/{prof}) saved to {out_p}")

    return True
