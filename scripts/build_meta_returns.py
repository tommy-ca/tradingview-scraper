import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

import numpy as np
import pandas as pd

sys.path.append(os.getcwd())
from tradingview_scraper.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("build_meta_returns")


def find_latest_run_for_profile(profile: str) -> Optional[Path]:
    runs_dir = Path("artifacts/summaries/runs")
    if not runs_dir.exists():
        return None

    # Sort runs by directory name (timestamp) descending
    runs = sorted([d for d in runs_dir.iterdir() if d.is_dir()], key=lambda x: x.name, reverse=True)

    for run in runs:
        # Priority 1: resolved_manifest.json
        manifest_path = run / "config" / "resolved_manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r") as f:
                    manifest = json.load(f)
                    if manifest.get("profile") == profile:
                        return run
            except Exception:
                pass

        # Priority 2: audit.jsonl genesis entry
        audit_path = run / "audit.jsonl"
        if audit_path.exists():
            try:
                with open(audit_path, "r") as f:
                    first_line = f.readline()
                    entry = json.loads(first_line)
                    if entry.get("type") == "genesis" and entry.get("profile") == profile:
                        return run
            except Exception:
                pass
    return None


def build_meta_returns(meta_profile: str, output_path: str, profiles: Optional[List[str]] = None, manifest_path: Path = Path("configs/manifest.json")):
    settings = get_settings()
    if not manifest_path.exists():
        logger.error(f"Manifest missing: {manifest_path}")
        return

    with open(manifest_path, "r") as f:
        full_manifest = json.load(f)

    profile_cfg = full_manifest.get("profiles", {}).get(meta_profile)
    if not profile_cfg:
        logger.error(f"Profile {meta_profile} not found in manifest")
        return

    sleeves = profile_cfg.get("sleeves", [])
    if not sleeves:
        logger.error(f"No sleeves defined for profile {meta_profile}")
        return

    # Tournament profiles to iterate through
    target_profiles = profiles or settings.profiles.split(",")
    logger.info(f"Target Meta Profiles: {target_profiles}")

    for prof in target_profiles:
        prof = prof.strip()
        meta_df = pd.DataFrame()
        sleeve_metadata = []

        logger.info(f"🔨 Building Meta-Matrix for profile: {prof}")

        for sleeve in sleeves:
            s_id = sleeve["id"]
            run_path = None

            # CR-837: Fractal Recursive Support
            # If sleeve is a meta-profile itself, resolve it first
            if "meta_profile" in sleeve:
                sub_meta = sleeve["meta_profile"]
                logger.info(f"  [{s_id}] Resolving nested meta-profile: {sub_meta}")

                # 1. Build Sub-Meta Returns
                sub_returns_file = Path("data/lakehouse") / f"meta_returns_{sub_meta}_{prof}.pkl"
                build_meta_returns(sub_meta, str(sub_returns_file), [prof], manifest_path)

                if not sub_returns_file.exists():
                    logger.warning(f"  [{s_id}] Failed to build sub-meta returns for {sub_meta}")
                    continue

                # 2. Optimize Sub-Meta (to get weights)
                from scripts.optimize_meta_portfolio import optimize_meta

                sub_opt_file = Path("data/lakehouse") / f"meta_optimized_{sub_meta}_{prof}.json"
                optimize_meta(str(sub_returns_file), str(sub_opt_file), profile=prof, meta_profile=sub_meta)

                if not sub_opt_file.exists():
                    logger.warning(f"  [{s_id}] Failed to optimize sub-meta {sub_meta}. Falling back to equal weight.")
                    s_rets_raw = pd.read_pickle(sub_returns_file)
                    s_rets = cast(pd.Series, s_rets_raw.mean(axis=1)).to_frame(s_id)
                else:
                    # 3. Calculate Weighted Sub-Meta Return
                    with open(sub_opt_file, "r") as f:
                        sub_opt_data = json.load(f)

                    sub_weights = {w["Symbol"]: w["Weight"] for w in sub_opt_data["weights"]}
                    s_rets_raw = pd.read_pickle(sub_returns_file)

                    # Align and Multiply
                    cols = [c for c in s_rets_raw.columns if c in sub_weights]
                    w_vec = np.array([sub_weights[c] for c in cols])
                    s_rets = (s_rets_raw[cols] * w_vec).sum(axis=1).to_frame(s_id)

                target_file = sub_returns_file  # For logging
            else:
                s_profile = sleeve["profile"]
                # CR-835: Respect explicit Run ID from manifest if provided
                s_run_id = sleeve.get("run_id")

                if s_run_id:
                    run_path = Path("artifacts/summaries/runs") / s_run_id
                    if not run_path.exists():
                        logger.warning(f"Explicit Run ID {s_run_id} not found in artifacts. Searching dynamically...")
                        run_path = find_latest_run_for_profile(s_profile)
                else:
                    run_path = find_latest_run_for_profile(s_profile)

                if not run_path:
                    logger.warning(f"Could not find a specific run for profile {s_profile}. Skipping.")
                    continue

                # Robust file discovery
                returns_dir = run_path / "data" / "returns"
                target_file = None

                if returns_dir.exists():
                    matching_files = list(returns_dir.glob(f"*_{prof}.pkl"))
                    if not matching_files:
                        if prof == "hrp":
                            matching_files = list(returns_dir.glob("*_min_variance.pkl"))

                        if not matching_files:
                            for fallback_prof in ["min_variance", "max_sharpe", "equal_weight"]:
                                fallback_files = list(returns_dir.glob(f"*_{fallback_prof}.pkl"))
                                if fallback_files:
                                    matching_files = fallback_files
                                    break

                    if matching_files:
                        matching_files.sort(key=lambda x: ("skfolio" not in x.name, x.name))
                        target_file = matching_files[0]
                    else:
                        fallbacks = list(returns_dir.glob("*_barbell.pkl"))
                        if fallbacks:
                            target_file = fallbacks[0]

                if target_file and target_file.exists():
                    s_rets_raw = pd.read_pickle(target_file)
                    if isinstance(s_rets_raw, pd.Series):
                        s_rets = s_rets_raw.to_frame(s_id)
                    elif isinstance(s_rets_raw, pd.DataFrame):
                        s_rets = s_rets_raw.iloc[:, 0].to_frame(s_id)
                    else:
                        logger.warning(f"  [{s_id}] Unknown return format in {target_file}")
                        continue
                else:
                    logger.warning(f"  [{s_id}] No return series found for {prof} in {run_path}")
                    continue

            # Robust Index Alignment (UTC Naive)
            s_rets.index = pd.to_datetime(s_rets.index)
            if s_rets.index.tz is not None:
                s_rets.index = s_rets.index.tz_convert(None)

            if meta_df.empty:
                meta_df = s_rets
            else:
                meta_df = meta_df.join(s_rets, how="inner")

            s_meta = {"id": s_id}
            if "meta_profile" in sleeve:
                s_meta["meta_profile"] = sleeve["meta_profile"]
            elif run_path is not None:
                s_meta.update({"profile": sleeve["profile"], "run_id": run_path.name, "run_path": str(run_path)})
            else:
                # Target file must have existed if we got here
                s_meta.update({"profile": sleeve.get("profile", "N/A"), "run_id": "N/A", "run_path": "N/A"})
            sleeve_metadata.append(s_meta)

        if not meta_df.empty:
            p_output_path = Path(output_path).parent / f"meta_returns_{meta_profile}_{prof}.pkl"
            os.makedirs(p_output_path.parent, exist_ok=True)
            meta_df.to_pickle(p_output_path)
            logger.info(f"✅ Meta-Returns ({meta_profile}/{prof}) saved to {p_output_path}")

            manifest_out = {"meta_profile": meta_profile, "risk_profile": prof, "sleeves": sleeve_metadata}
            m_path = Path("data/lakehouse") / f"meta_manifest_{meta_profile}_{prof}.json"
            with open(m_path, "w") as f:
                json.dump(manifest_out, f, indent=2)

    # Maintain legacy output_path for compatibility with old scripts if needed
    # but we now favor the profile-matrix outputs.
    logger.info("Meta-Matrix construction complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, help="Meta portfolio profile name")
    parser.add_argument("--output", default="data/lakehouse/meta_returns.pkl")
    parser.add_argument("--profiles", help="Comma-separated risk profiles to build")
    args = parser.parse_args()

    target_profs = args.profiles.split(",") if args.profiles else None
    build_meta_returns(args.profile, args.output, target_profs)
