import argparse
import json
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

sys.path.append(os.getcwd())

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("flatten_meta_weights")


def flatten_weights(meta_weights_path: str, meta_manifest_path: str, output_path: str, profile: Optional[str] = None):
    # Handle Profile Matrix
    target_profile = profile or "barbell"  # Default legacy

    # Resolve meta weights path based on profile
    if profile:
        p_weights_path = str(Path("data/lakehouse") / f"meta_optimized_{target_profile}.json")
        if os.path.exists(p_weights_path):
            meta_weights_path = p_weights_path

    # Fallback if profile not found or not provided
    if not os.path.exists(meta_weights_path):
        fallback_path = str(Path("data/lakehouse") / f"meta_optimized_{target_profile}.json")
        if os.path.exists(fallback_path):
            meta_weights_path = fallback_path

    if not os.path.exists(meta_weights_path):
        logger.error(f"Meta-weights missing: {meta_weights_path}")
        return

    logger.info(f"Loading meta-weights from: {meta_weights_path}")

    # Try to find the specific manifest for the profile
    if profile:
        p_manifest_path = str(Path("data/lakehouse") / f"meta_manifest_{profile}.json")
        if os.path.exists(p_manifest_path):
            meta_manifest_path = p_manifest_path

    if not os.path.exists(meta_manifest_path):
        logger.error(f"Meta-manifest missing: {meta_manifest_path}")
        return

    with open(meta_weights_path, "r") as f:
        meta_weights_data = json.load(f)

    with open(meta_manifest_path, "r") as f:
        meta_manifest = json.load(f)

    sleeve_weights = {w["Symbol"]: w["Weight"] for w in meta_weights_data["weights"]}
    sleeve_runs = {s["id"]: s["run_path"] for s in meta_manifest["sleeves"]}

    final_assets = defaultdict(float)
    asset_details = {}

    for s_id, s_weight in sleeve_weights.items():
        run_path = sleeve_runs.get(s_id)
        if not run_path:
            logger.warning(f"No run path found for sleeve {s_id}")
            continue

        logger.info(f"Extracting weights for sleeve {s_id} (profile: {target_profile}) from {run_path}")

        # CR-831: Workspace Isolation Aware Extraction
        # Try prioritized isolated paths
        search_paths = [
            Path(run_path) / "data" / "portfolio_optimized_v2.json",
            Path(run_path) / "data" / "metadata" / "portfolio_optimized_v2.json",
            Path(run_path) / "portfolio_optimized_v2.json",
        ]

        opt_path = None
        for sp in search_paths:
            if sp.exists():
                opt_path = sp
                break

        found_weights = False
        if opt_path:
            with open(opt_path, "r") as f:
                opt_data = json.load(f)

            if "profiles" in opt_data:
                # Target the EXACT fractal profile
                p_data = opt_data["profiles"].get(target_profile)
                if p_data and "assets" in p_data:
                    for asset in p_data["assets"]:
                        sym = asset["Symbol"]
                        w = asset["Weight"]
                        final_assets[sym] += w * s_weight
                        asset_details[sym] = asset
                    found_weights = True

        if not found_weights:
            # Fallback to tournament results (Top 5)
            results_path = Path(run_path) / "data" / "tournament_results.json"
            if results_path.exists():
                with open(results_path, "r") as f:
                    results_data = json.load(f)
                try:
                    # Assume cvxportfolio/skfolio/target_profile
                    profile_data = results_data["results"]["cvxportfolio"]["skfolio"][target_profile]
                    last_window = profile_data["windows"][-1]
                    top_assets = last_window["top_assets"]
                    for asset in top_assets:
                        sym = asset["Symbol"]
                        w = asset["Weight"]
                        final_assets[sym] += w * s_weight
                        asset_details[sym] = asset
                    found_weights = True
                except Exception:
                    pass

        if not found_weights:
            logger.warning(f"Could not find weights for profile {target_profile} in sleeve {s_id}")

    # Construct final portfolio
    output_weights = []
    for sym, weight in sorted(final_assets.items(), key=lambda x: x[1], reverse=True):
        detail = asset_details.get(sym, {})
        output_weights.append(
            {
                "Symbol": sym,
                "Weight": weight,
                "Description": detail.get("Description", "N/A"),
                "Sector": detail.get("Sector", "N/A"),
                "Market": detail.get("Market", "UNKNOWN"),
                "Type": detail.get("Type", "CORE"),
            }
        )

    result = {
        "metadata": {"meta_profile": meta_manifest["meta_profile"], "risk_profile": target_profile, "sleeve_weights": sleeve_weights, "generated_at": str(pd.Timestamp.now())},
        "weights": output_weights,
    }

    # Save profile-specific output
    p_output_path = Path(output_path).parent / f"portfolio_optimized_meta_{target_profile}.json"
    os.makedirs(os.path.dirname(p_output_path), exist_ok=True)
    with open(p_output_path, "w") as f:
        json.dump(result, f, indent=2)

    logger.info(f"Flattened meta-portfolio ({target_profile}) saved to {p_output_path}")
    logger.info(f"Total assets: {len(output_weights)}")


if __name__ == "__main__":
    from typing import Optional

    import pandas as pd

    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", default="data/lakehouse/meta_optimized.json")
    parser.add_argument("--manifest", default="data/lakehouse/meta_manifest.json")
    parser.add_argument("--output", default="data/lakehouse/portfolio_optimized_meta.json")
    parser.add_argument("--profile", help="Specific risk profile to flatten")
    args = parser.parse_args()

    flatten_weights(args.weights, args.manifest, args.output, args.profile)
