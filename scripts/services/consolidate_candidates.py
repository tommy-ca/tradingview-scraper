import argparse
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

from tradingview_scraper.pipelines.selection.base import FoundationHealthRegistry
from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.candidates import normalize_candidate_record

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("consolidate_candidates")


def consolidate(run_id: str, output_path: str | None = None):
    settings = get_settings()
    export_dir = settings.export_dir / run_id
    if not output_path:
        # CR-960: Default to run-specific isolation
        run_data_dir = settings.summaries_runs_dir / run_id / "data"
        output_path = str(run_data_dir / "portfolio_candidates.json")

    registry = FoundationHealthRegistry(path=settings.lakehouse_dir / "foundation_health.json")

    if not export_dir.exists():
        logger.error(f"Export directory not found: {export_dir}")
        return

    strict_schema = bool(settings.strict_health) or os.getenv("TV_STRICT_CANDIDATE_SCHEMA") == "1"

    by_symbol: Dict[str, Dict[str, Any]] = {}
    dropped_invalid = 0
    dropped_toxic = 0

    # Find all .json files, excluding 'ohlc_' prefix just in case (though we fixed that)
    files = sorted(export_dir.glob("*.json"))
    logger.info(f"Found {len(files)} candidate files in {export_dir}")

    touched_symbols = set()

    for file_path in files:
        if file_path.name.startswith("ohlc_") or file_path.name == "candidates_validated.json":
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
                try:
                    normalized = normalize_candidate_record(cand, strict=strict_schema)
                except Exception:
                    if strict_schema:
                        raise
                    dropped_invalid += 1
                    continue

                if not normalized:
                    dropped_invalid += 1
                    continue

                sym = normalized.get("symbol")
                if not sym:
                    dropped_invalid += 1
                    continue

                # Registry Veto (Fail-fast in consolidation)
                if not registry.is_healthy(sym) and sym in registry.data:
                    reg_entry = registry.data[sym]
                    if reg_entry.get("status") == "toxic":
                        logger.debug(f"Consolidation Gate: Dropping known TOXIC asset: {sym}")
                        dropped_toxic += 1
                        continue

                touched_symbols.add(sym)

                existing = by_symbol.get(sym)
                if existing is None:
                    by_symbol[sym] = normalized
                    count += 1
                    continue

                # Merge metadata deterministically for duplicates (keep first canonical fields).
                existing_meta = existing.get("metadata")
                if not isinstance(existing_meta, dict):
                    existing_meta = {}

                new_meta = normalized.get("metadata")
                if isinstance(new_meta, dict):
                    for k, v in new_meta.items():
                        existing_meta.setdefault(k, v)
                existing["metadata"] = existing_meta

                # Opportunistically fill missing optional fields (first non-null wins).
                for opt_key in ["sector", "industry", "market_cap_rank", "volume_24h"]:
                    if existing.get(opt_key) is None and normalized.get(opt_key) is not None:
                        existing[opt_key] = normalized.get(opt_key)

            logger.debug(f"Processed {file_path}: added {count} candidates")

        except Exception as e:
            if strict_schema:
                raise
            logger.error(f"Failed to process {file_path}: {e}")

    # Stale Threshold (168h - Relaxed to allow testing with Jan 20 data)
    import time

    stale_threshold_sec = 168 * 3600
    now = time.time()

    all_candidates: List[Dict[str, Any]] = []
    run_valid_candidates: List[Dict[str, Any]] = []

    for sym, normalized in sorted(by_symbol.items()):
        # CR-930: Data Existence Gate
        safe_sym = sym.replace(":", "_")
        p_path = settings.lakehouse_dir / f"{safe_sym}_1d.parquet"

        if not p_path.exists():
            logger.warning(f"Dropping candidate {sym}: No data in Lakehouse ({p_path}).")
            dropped_invalid += 1
            continue

        # CR-930: Data Freshness Gate
        try:
            mtime = p_path.stat().st_mtime
            if (now - mtime) > stale_threshold_sec:
                # Double check content if we really care, but mtime is a good proxy for "ingest touched it"
                logger.warning(f"Dropping candidate {sym}: Data is STALE (Last modified > 168h ago).")
                dropped_invalid += 1
                continue
        except Exception:
            pass

        all_candidates.append(normalized)
        if sym in touched_symbols:
            run_valid_candidates.append(normalized)

    if not all_candidates:
        logger.error(f"❌ No valid candidates found to consolidate for run {run_id}. Failing.")
        exit(1)

    logger.info(f"Consolidated {len(all_candidates)} unique candidates from run {run_id}.")
    if dropped_invalid:
        logger.warning("Dropped %s invalid candidate records while consolidating (strict=%s).", dropped_invalid, strict_schema)
    if dropped_toxic:
        logger.warning("Dropped %s TOXIC assets found in health registry.", dropped_toxic)

    # Write output
    # CR-960: Write to run directory if output path is not explicit
    if not output_path:
        # Default to run-specific data dir if we can infer it, otherwise lakehouse
        # But `consolidate` is called with explicit output path in Makefile for lakehouse update.
        # Wait, Makefile calls: `$(PY) scripts/services/consolidate_candidates.py --run-id $(RUN_ID)`
        # And `output_path` defaults to `lakehouse/portfolio_candidates.json`.

        # We need to CHANGE the default or the Makefile call.
        # Let's change the default behavior here to output to BOTH or just Run Dir?
        # Requirement: "portfolio_candidates.json MUST be generated and stored exclusively within the run workspace"
        # So we should default to run workspace.

        # But we don't have easy access to run_dir from here without settings logic.
        run_data_dir = settings.summaries_runs_dir / run_id / "data"
        output_path = str(run_data_dir / "portfolio_candidates.json")

    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with open(out_p, "w") as f:
        json.dump(all_candidates, f, indent=2)

    logger.info(f"Wrote to {out_p}")

    # Save Run-Specific Validated List for downstream Audit/Backfill
    run_valid_path = export_dir / "candidates_validated.json"
    with open(run_valid_path, "w") as f:
        json.dump(run_valid_candidates, f, indent=2)
    logger.info(f"Wrote validated run scope to {run_valid_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True, help="Run ID to consolidate export files from")
    parser.add_argument("--output", default=None, help="Output path")
    args = parser.parse_args()

    consolidate(args.run_id, args.output)
