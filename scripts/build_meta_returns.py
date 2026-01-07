import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

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
        manifest_path = run / "config" / "resolved_manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r") as f:
                    manifest = json.load(f)
                    # In resolved_manifest.json, 'profile' is usually at the root
                    if manifest.get("profile") == profile:
                        return run
            except Exception:
                continue
    return None


def build_meta_returns(meta_profile: str, output_path: str):
    settings = get_settings()
    manifest_path = Path("configs/manifest.json")
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

    meta_df = pd.DataFrame()

    for sleeve in sleeves:
        s_id = sleeve["id"]
        s_profile = sleeve["profile"]

        logger.info(f"Processing sleeve: {s_id} (profile: {s_profile})")

        # Strategy: find the latest run of this profile
        # Note: If no recent run exists, this sleeve will be missing.
        run_path = find_latest_run_for_profile(s_profile)
        if not run_path:
            # Fallback: check if 'latest' symlink matches the profile
            # (This is risky if 'latest' is a different profile)
            logger.warning(f"Could not find a specific run for profile {s_profile}. Skipping.")
            continue

        # Try to load the 'champion' return series
        # Priority: cvxportfolio_skfolio_barbell -> cvxportfolio_skfolio_hrp -> cvxportfolio_skfolio_benchmark
        potential_files = ["cvxportfolio_skfolio_barbell.pkl", "cvxportfolio_skfolio_hrp.pkl", "cvxportfolio_skfolio_benchmark.pkl"]

        found_sleeve_rets = False
        for f_name in potential_files:
            p = run_path / "data" / "returns" / f_name
            if p.exists():
                logger.info(f"  Found returns: {p}")
                s_rets = pd.read_pickle(p)
                if isinstance(s_rets, pd.Series):
                    s_rets = s_rets.to_frame(s_id)
                else:
                    # If it's a DF, take the first column
                    s_rets = s_rets.iloc[:, 0].to_frame(s_id)

                if meta_df.empty:
                    meta_df = s_rets
                else:
                    meta_df = meta_df.join(s_rets, how="inner")
                found_sleeve_rets = True
                break

        if not found_sleeve_rets:
            logger.warning(f"  No return series found for sleeve {s_id} in {run_path}")

    if meta_df.empty:
        logger.error("No sleeve returns collected. Meta-Returns is empty.")
        return

    logger.info(f"Meta-Returns constructed. Shape: {meta_df.shape}")
    logger.info(f"Columns: {list(meta_df.columns)}")
    logger.info(f"Date Range: {meta_df.index[0]} to {meta_df.index[-1]}")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    meta_df.to_pickle(output_path)
    logger.info(f"Saved to {output_path}")

    # Output manifest for flattening
    manifest_out = {"meta_profile": meta_profile, "sleeves": []}
    for sleeve in sleeves:
        s_id = sleeve["id"]
        s_profile = sleeve["profile"]
        run_path = find_latest_run_for_profile(s_profile)
        if run_path:
            manifest_out["sleeves"].append({"id": s_id, "profile": s_profile, "run_id": run_path.name, "run_path": str(run_path)})

    manifest_path = Path("data/lakehouse/meta_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest_out, f, indent=2)
    logger.info(f"Meta-Manifest saved to {manifest_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, help="Meta portfolio profile name")
    parser.add_argument("--output", default="data/lakehouse/meta_returns.pkl")
    args = parser.parse_args()

    build_meta_returns(args.profile, args.output)
