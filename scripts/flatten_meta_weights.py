import argparse
import json
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.append(os.getcwd())

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("flatten_meta_weights")


def flatten_weights(meta_weights_path: str, meta_manifest_path: str, output_path: str):
    if not os.path.exists(meta_weights_path):
        logger.error(f"Meta-weights missing: {meta_weights_path}")
        return
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

        # Load the optimized portfolio for this sleeve
        # Usually it's portfolio_optimized_v2.json in the data dir or root?
        # In a run dir, it's typically artifacts/summaries/runs/<RUN_ID>/data/tournament_results.json
        # or we look for the optimized weights in the lakehouse of that run.

        # Actually, let's look for artifacts/summaries/runs/<RUN_ID>/tearsheets/cvxportfolio/skfolio/barbell/report.json (if exists)
        # OR we look at data/lakehouse/portfolio_optimized_v2.json IF the run is recent.
        # But we want the weights from THAT specific run.

        # Let's try to find weights in the tournament_results.json of that run
        results_path = Path(run_path) / "data" / "tournament_results.json"
        if not results_path.exists():
            logger.warning(f"No tournament results found in {run_path}")
            continue

        with open(results_path, "r") as f:
            results_data = json.load(f)

        # Find the 'barbell' weights for 'skfolio' engine in 'cvxportfolio' simulator (standard production)
        # We'll take the LAST window weights
        try:
            profile_data = results_data["results"]["cvxportfolio"]["skfolio"]["barbell"]
            last_window = profile_data["windows"][-1]
            top_assets = last_window["top_assets"]  # Note: this might only be top 5

            # If top_assets is limited, we might need a better source.
            # Usually, the full weights are in the audit logs or we need to extract from tournament_results.json deeper.
            # Wait, tournament_results.json doesn't store FULL weights for all assets in all windows to save space?
            # Actually, let's check.

            logger.info(f"Extracting weights for sleeve {s_id} from {run_path}")

            # Fallback: check artifacts/summaries/runs/<RUN_ID>/data/metadata/portfolio_optimized_v2.json
            opt_path = Path(run_path) / "data" / "metadata" / "portfolio_optimized_v2.json"
            if not opt_path.exists():
                # Try lakehouse dir if it was archived
                opt_path = Path(run_path) / "portfolio_optimized_v2.json"

            if opt_path.exists():
                with open(opt_path, "r") as f:
                    opt_data = json.load(f)

                # Different engines might have different formats
                # If it's the new multi-winner manifest:
                if "winners" in opt_data:
                    # Find skfolio/barbell
                    weights = None
                    for w in opt_data["winners"]:
                        if w["engine"] == "skfolio" and w["profile"] == "barbell":
                            weights = w["weights"]
                            break
                    if weights:
                        for asset in weights:
                            sym = asset["Symbol"]
                            w = asset["Weight"]
                            final_assets[sym] += w * s_weight
                            asset_details[sym] = asset
                else:
                    # Legacy format (single weights list)
                    for asset in opt_data:
                        sym = asset["Symbol"]
                        w = asset["Weight"]
                        final_assets[sym] += w * s_weight
                        asset_details[sym] = asset
            else:
                logger.warning(f"Could not find full weights for sleeve {s_id}. Using top_assets from last window.")
                for asset in top_assets:
                    sym = asset["Symbol"]
                    w = asset["Weight"]
                    final_assets[sym] += w * s_weight
                    asset_details[sym] = asset

        except Exception as e:
            logger.error(f"Error processing sleeve {s_id}: {e}")

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

    result = {"metadata": {"meta_profile": meta_manifest["meta_profile"], "sleeve_weights": sleeve_weights, "generated_at": str(pd.Timestamp.now())}, "weights": output_weights}

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    logger.info(f"Flattened meta-portfolio saved to {output_path}")
    logger.info(f"Total assets: {len(output_weights)}")


if __name__ == "__main__":
    import pandas as pd

    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", default="data/lakehouse/meta_optimized.json")
    parser.add_argument("--manifest", default="data/lakehouse/meta_manifest.json")
    parser.add_argument("--output", default="data/lakehouse/portfolio_optimized_meta.json")
    args = parser.parse_args()

    flatten_weights(args.weights, args.manifest, args.output)
