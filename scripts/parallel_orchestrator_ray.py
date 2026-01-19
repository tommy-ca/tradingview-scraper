import logging
import os
import subprocess
import sys
import time
from typing import Dict, List

import ray

logger = logging.getLogger("ray_orchestrator")


@ray.remote(num_cpus=2, memory=3 * 1024 * 1024 * 1024)
def run_sleeve_production(profile: str, run_id: str) -> Dict:
    """
    Executes a single sleeve's production pipeline as a Ray task.
    """
    start_time = time.time()
    logger.info(f"🚀 [Ray] Starting production for {profile} (Run: {run_id})")

    # CR-FIX: Ensure we run in the correct working directory and use same python
    cwd = os.getcwd()
    cmd = [sys.executable, "-m", "scripts.run_production_pipeline", "--profile", profile, "--run-id", run_id]

    # Explicitly inherit and propagate important environment variables
    env = os.environ.copy()
    env["PYTHONPATH"] = cwd + ":" + env.get("PYTHONPATH", "")
    env["TV_PROFILE"] = profile
    env["TV_RUN_ID"] = run_id

    # Force use of local python for Ray tasks
    env["PATH"] = os.path.dirname(sys.executable) + ":" + env.get("PATH", "")

    try:
        # Capture output to prevent interleaving
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=cwd, env=env)
        duration = time.time() - start_time
        return {"profile": profile, "run_id": run_id, "status": "success", "duration": duration, "stdout_tail": result.stdout[-500:]}
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ [Ray] Task failed for {profile}: {e}")
        logger.error(f"STDOUT: {e.stdout}")
        logger.error(f"STDERR: {e.stderr}")
        return {"profile": profile, "run_id": run_id, "status": "error", "error": str(e), "stderr": e.stderr}


def execute_parallel_sleeves(sleeves: List[Dict]) -> List[Dict]:
    """
    Orchestrates multiple sleeve runs using Ray.
    """
    if not ray.is_initialized():
        # CR-FIX: Standard init. Subprocesses will use the local env
        # since we are running on a single node.
        ray.init(ignore_reinit_error=True)

    futures = [run_sleeve_production.remote(s["profile"], s["run_id"]) for s in sleeves]

    results = ray.get(futures)
    return results
