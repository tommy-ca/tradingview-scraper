import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("consolidate_candidates")


def consolidate(run_id: str, output_path: str = "data/lakehouse/portfolio_candidates.json"):
    export_dir = Path(f"export/{run_id}")
    if not export_dir.exists():
        logger.error(f"Export directory not found: {export_dir}")
        return

    all_candidates: List[Dict[str, Any]] = []
    seen_symbols = set()

    # Find all .json files, excluding 'ohlc_' prefix just in case (though we fixed that)
    files = list(export_dir.glob("*.json"))
    logger.info(f"Found {len(files)} candidate files in {export_dir}")

    for file_path in files:
        if file_path.name.startswith("ohlc_"):
            continue

        try:
            with open(file_path, "r") as f:
                content = json.load(f)

            # Handle {meta, data} envelope
            candidates = []
            if isinstance(content, dict):
                if "data" in content and isinstance(content["data"], list):
                    candidates = content["data"]
                elif "symbol" in content:  # Single object? Unlikely based on schema
                    candidates = [content]
            elif isinstance(content, list):
                candidates = content

            # Extract and dedup
            count = 0
            for cand in candidates:
                if not isinstance(cand, dict):
                    continue
                sym = cand.get("symbol")
                if sym and sym not in seen_symbols:
                    all_candidates.append(cand)
                    seen_symbols.add(sym)
                    count += 1

            logger.debug(f"Processed {file_path}: added {count} candidates")

        except Exception as e:
            logger.error(f"Failed to process {file_path}: {e}")

    logger.info(f"Consolidated {len(all_candidates)} unique candidates from run {run_id}.")

    # Write output
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with open(out_p, "w") as f:
        json.dump(all_candidates, f, indent=2)

    logger.info(f"Wrote to {out_p}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True, help="Run ID to consolidate export files from")
    parser.add_argument("--output", default="data/lakehouse/portfolio_candidates.json", help="Output path")
    args = parser.parse_args()

    consolidate(args.run_id, args.output)
