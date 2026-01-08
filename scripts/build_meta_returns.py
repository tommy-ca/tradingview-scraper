import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

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


def build_meta_returns(meta_profile: str, output_path: str, profiles: Optional[List[str]] = None):
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
            s_profile = sleeve["profile"]

            run_path = find_latest_run_for_profile(s_profile)
            if not run_path:
                logger.warning(f"Could not find a specific run for profile {s_profile}. Skipping.")
                continue

            # Target the specific profile's return stream
            # Optimized filenames: cvxportfolio_skfolio_<prof>.pkl
            f_name = f"cvxportfolio_skfolio_{prof}.pkl"
            p = run_path / "data" / "returns" / f_name

            if not p.exists():
                # Fallback to standard filename if the profile was different
                p = run_path / "data" / "returns" / "cvxportfolio_skfolio_barbell.pkl"

            if p.exists():
                logger.info(f"  [{s_id}] Found returns: {p.name}")
                s_rets = pd.read_pickle(p)
                if isinstance(s_rets, pd.Series):
                    s_rets = s_rets.to_frame(s_id)
                else:
                    s_rets = s_rets.iloc[:, 0].to_frame(s_id)

                if meta_df.empty:
                    meta_df = s_rets
                else:
                    meta_df = meta_df.join(s_rets, how="inner")

                sleeve_metadata.append({"id": s_id, "profile": s_profile, "run_id": run_path.name, "run_path": str(run_path)})
            else:
                logger.warning(f"  [{s_id}] No return series found for {prof} in {run_path}")

        if not meta_df.empty:
            # Save profile-specific meta returns
            p_output_path = Path(output_path).parent / f"meta_returns_{prof}.pkl"
            os.makedirs(p_output_path.parent, exist_ok=True)
            meta_df.to_pickle(p_output_path)
            logger.info(f"✅ Meta-Returns ({prof}) saved to {p_output_path}")

            # Also output a manifest for this specific profile matrix
            manifest_out = {"meta_profile": meta_profile, "risk_profile": prof, "sleeves": sleeve_metadata}
            m_path = Path("data/lakehouse") / f"meta_manifest_{prof}.json"
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
