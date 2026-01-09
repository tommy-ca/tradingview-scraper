import os
import subprocess
from typing import Optional

from prefect import flow, get_run_logger, task


@task(name="Cleanup", retries=2)
def cleanup(profile: str, manifest: str):
    logger = get_run_logger()
    logger.info(f"Cleaning up run artifacts for profile: {profile}")
    subprocess.check_call(["make", f"PROFILE={profile}", f"MANIFEST={manifest}", "clean-run"])


@task(name="Discovery")
def discovery(profile: str, manifest: str):
    logger = get_run_logger()
    logger.info(f"Executing discovery scanners for profile: {profile}")
    subprocess.check_call(["make", f"PROFILE={profile}", f"MANIFEST={manifest}", "scan-run"])


@task(name="Data Aggregation")
def aggregate_data(profile: str, manifest: str):
    logger = get_run_logger()
    logger.info("Aggregating raw pool candidates...")
    subprocess.check_call(["make", f"PROFILE={profile}", f"MANIFEST={manifest}", "data-prep-raw"])


@task(name="Data Ingestion")
def fetch_data(profile: str, manifest: str, lookback: int = 500):
    logger = get_run_logger()
    logger.info(f"Fetching {lookback} days of history...")
    subprocess.check_call(["make", f"PROFILE={profile}", f"MANIFEST={manifest}", f"LOOKBACK={lookback}", "data-fetch"])


@task(name="Natural Selection")
def natural_selection(profile: str, manifest: str):
    logger = get_run_logger()
    logger.info("Executing Natural Selection...")
    subprocess.check_call(["make", f"PROFILE={profile}", f"MANIFEST={manifest}", "port-select"])


@task(name="Persistence Analysis")
def persistence_analysis(profile: str, manifest: str):
    logger = get_run_logger()
    logger.info("Executing Persistence Analysis...")
    subprocess.check_call(["make", f"PROFILE={profile}", f"MANIFEST={manifest}", "research-persistence"])


@task(name="Backtest Tournament")
def backtest_tournament(profile: str, manifest: str, use_ray: bool = True):
    logger = get_run_logger()
    logger.info(f"Executing Backtest Tournament (Ray Enabled: {use_ray})...")
    env = os.environ.copy()
    env["TV_USE_RAY"] = "1" if use_ray else "0"
    subprocess.check_call(["make", f"PROFILE={profile}", f"MANIFEST={manifest}", "port-test"], env=env)


@flow(name="Institutional Production Pipeline")
def production_flow(profile: str = "production", manifest: str = "configs/manifest.json", lookback: Optional[int] = None, skip_backtest: bool = False):
    logger = get_run_logger()

    # Initialize Ray if enabled
    use_ray = os.getenv("TV_USE_RAY", "1") == "1"
    if use_ray:
        import ray

        if not ray.is_initialized():
            logger.info("Initializing Ray (Local Mode PoC)...")
            # Use local_mode=True to validate integration logic in PoC
            ray.init(ignore_reinit_error=True, local_mode=True)

    cleanup(profile, manifest)
    discovery(profile, manifest)
    aggregate_data(profile, manifest)

    # Fetch lookback from manifest if not provided
    lb = lookback if lookback is not None else 60  # Default to 60 for safety in flow

    # Lightweight fetch for selection
    fetch_data(profile, manifest, lookback=60)
    natural_selection(profile, manifest)

    # High-integrity fetch for analysis/backtest
    # For development, we keep it small
    lb_final = lookback if lookback is not None else (60 if profile == "development" else 500)
    fetch_data(profile, manifest, lookback=lb_final)

    persistence_analysis(profile, manifest)

    if not skip_backtest:
        backtest_tournament(profile, manifest, use_ray=use_ray)


if __name__ == "__main__":
    production_flow(profile="development")
