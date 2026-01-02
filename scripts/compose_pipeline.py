import argparse
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

import yaml

from tradingview_scraper.futures_universe_selector import SelectorConfig, _load_config_file

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def compose_pipeline(pipeline_config: Dict[str, Any], profile_name: str) -> List[Dict[str, Any]]:
    """
    Composes a list of full scanner configurations from a pipeline definition.
    """
    scanners = pipeline_config.get("scanners", [])
    interval = pipeline_config.get("interval", "1d")

    composed_configs = []
    for scanner_path in scanners:
        # Resolve path relative to configs/
        full_path = Path("configs") / scanner_path
        if not full_path.exists() and not full_path.suffix:
            full_path = full_path.with_suffix(".yaml")

        if not full_path.exists():
            logger.error(f"Scanner config not found: {full_path}")
            continue

        logger.info(f"Composing scanner: {scanner_path} (Interval: {interval})")
        config_dict = _load_config_file(str(full_path))

        # Inject pipeline-level overrides
        if "trend" not in config_dict:
            config_dict["trend"] = {}
        config_dict["trend"]["timeframe_loader"] = interval  # Store for ingestion

        # Validate with Pydantic
        try:
            SelectorConfig(**config_dict)
            composed_configs.append(config_dict)
        except Exception as e:
            logger.error(f"Validation failed for {scanner_path}: {e}")

    return composed_configs


def main():
    parser = argparse.ArgumentParser(description="Compose and execute discovery pipelines.")
    parser.add_argument("--profile", type=str, default="production_2026_q1", help="Manifest profile to use")
    parser.add_argument("--pipeline", type=str, help="Specific pipeline to run (optional)")
    parser.add_argument("--config-json", type=str, help="Tactical JSON overrides (merged into final config)")
    parser.add_argument("--dry-run", action="store_true", help="Only compose and validate, don't execute")

    args = parser.parse_args()

    # Load manifest
    manifest_path = Path("configs/manifest.json")
    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    profile = manifest.get("profiles", {}).get(args.profile)

    # Resolve Alias
    visited = {args.profile}
    while isinstance(profile, str):
        if profile in visited:
            logger.error(f"Circular alias: {' -> '.join(visited)} -> {profile}")
            return
        visited.add(profile)
        profile = manifest.get("profiles", {}).get(profile)

    if not profile:
        logger.error(f"Profile {args.profile} not found in manifest")
        return

    discovery = profile.get("discovery", {})
    pipelines = discovery.get("pipelines", {})

    target_pipelines = [args.pipeline] if args.pipeline else list(pipelines.keys())

    # Parse CLI Overrides
    cli_overrides = {}
    if args.config_json:
        try:
            cli_overrides = json.loads(args.config_json)
        except Exception as e:
            logger.error(f"Failed to parse --config-json: {e}")
            return

    all_composed = []
    for p_name in target_pipelines:
        p_config = pipelines.get(p_name)
        if not p_config:
            logger.warning(f"Pipeline {p_name} not found")
            continue

        composed_batch = compose_pipeline(p_config, args.profile)

        # Apply CLI Overrides to each config in batch
        for config in composed_batch:
            if cli_overrides:
                # Basic merge
                config.update(cli_overrides)
            all_composed.append(config)

    logger.info(f"Total composed scanners: {len(all_composed)}")

    if args.dry_run:
        logger.info("Dry run complete. Validation successful.")
        return

    # Execution Phase
    from tradingview_scraper.futures_universe_selector import main as run_selector

    for config in all_composed:
        logger.info(f"Executing scanner: {config.get('export_metadata', {}).get('symbol')}")
        # We need a way to pass the dict directly to the selector's main or equivalent
        # For now, we'll write to a temp file
        temp_path = "configs/temp_composed.yaml"
        with open(temp_path, "w") as f:
            yaml.dump(config, f)

        try:
            # Re-initialize sys.argv for the selector main
            import sys

            old_argv = sys.argv
            sys.argv = ["futures_universe_selector", "--config", temp_path, "--export", "json"]
            run_selector()
            sys.argv = old_argv
        except Exception as e:
            logger.error(f"Execution failed: {e}")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


if __name__ == "__main__":
    main()
