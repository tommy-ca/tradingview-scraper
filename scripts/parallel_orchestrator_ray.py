import logging
import subprocess
import time
from typing import Dict, List

import ray

logger = logging.getLogger("ray_orchestrator")


@ray.remote(num_cpus=2)
def run_sleeve_production(profile: str, run_id: str) -> Dict:
    """
    Executes a single sleeve's production pipeline as a Ray task.
    """
    start_time = time.time()
    logger.info(f"🚀 [Ray] Starting production for {profile} (Run: {run_id})")

    cmd = ["uv", "run", "python", "-m", "scripts.run_production_pipeline", "--profile", profile, "--run-id", run_id]

    try:
        # Capture output to prevent interleaving
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration = time.time() - start_time
        return {"profile": profile, "run_id": run_id, "status": "success", "duration": duration, "stdout_tail": result.stdout[-500:]}
    except subprocess.CalledProcessError as e:
        return {"profile": profile, "run_id": run_id, "status": "error", "error": str(e), "stderr": e.stderr}


def execute_parallel_sleeves(sleeves: List[Dict]) -> List[Dict]:
    """
    Orchestrates multiple sleeve runs using Ray.
    """
    if not ray.is_initialized():
        ray.init(ignore_reinit_error=True)

    futures = [run_sleeve_production.remote(s["profile"], s["run_id"]) for s in sleeves]

    results = ray.get(futures)
    return results
