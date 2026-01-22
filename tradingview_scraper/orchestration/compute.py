import logging
import os
from typing import Any, Dict, List, Optional

import ray

from tradingview_scraper.orchestration.sleeve_executor import SleeveActor
from tradingview_scraper.telemetry.tracing import trace_span

logger = logging.getLogger(__name__)


class RayComputeEngine:
    """
    Central manager for the Ray cluster and parallel task dispatch.
    Handles resource allocation and sleeve execution with process isolation.
    """

    def __init__(self, num_cpus: Optional[int] = None, memory_limit: Optional[int] = None):
        self.num_cpus = num_cpus
        self.memory_limit = memory_limit
        self._is_managed = False

    def __enter__(self):
        self._is_managed = True
        self.ensure_initialized()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._is_managed:
            self.shutdown()

    def shutdown(self):
        """Gracefully shuts down the Ray cluster if initialized."""
        if ray.is_initialized():
            logger.info("Shutting down Ray cluster")
            ray.shutdown()

    def ensure_initialized(self):
        """Standard Ray initialization if not already active."""
        if not ray.is_initialized():
            # CR-FIX: Support aggressive resource capping for constrained environments
            env_cpus = os.getenv("TV_ORCH_CPUS")
            if env_cpus:
                self.num_cpus = int(env_cpus)
            elif not self.num_cpus and os.cpu_count():
                self.num_cpus = min(2, os.cpu_count() or 1)

            logger.info(f"Initializing Ray with {self.num_cpus or 'default'} CPUs")

            # Runtime environment setup: exclude heavy folders to avoid copy overhead
            runtime_env = {"working_dir": ".", "excludes": ["data", ".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", ".opencode"]}

            ray.init(
                num_cpus=self.num_cpus,
                ignore_reinit_error=True,
                runtime_env=runtime_env,
                _system_config={
                    "object_spilling_threshold": 0.8,
                },
            )

    @trace_span("execute_sleeves")
    def execute_sleeves(self, sleeves: List[Dict[str, str]]) -> List[Dict]:
        """
        Execute multiple strategy sleeves in parallel using stateful Native Actors.
        Ensures each sleeve has an isolated process environment.
        """
        self.ensure_initialized()

        host_cwd = os.getcwd()
        env_vars = self._capture_env()

        logger.info(f"Dispatching {len(sleeves)} sleeves to Ray cluster.")

        # 1. Spawn Actors (One per sleeve for total isolation)
        actors = [SleeveActor.remote(host_cwd, env_vars) for _ in sleeves]

        # 2. Dispatch Pipeline Tasks
        futures = [a.run_pipeline.remote(s["profile"], s["run_id"]) for a, s in zip(actors, sleeves)]

        # 3. Collect Results
        results = ray.get(futures)

        # 4. Cleanup Actors
        for a in actors:
            ray.kill(a)

        return results

    def _capture_env(self) -> Dict[str, str]:
        """Captures relevant environment variables to propagate to workers."""
        return {k: v for k, v in os.environ.items() if k.startswith("TV_") or k in ["PYTHONPATH", "PATH", "UV_PROJECT_ENVIRONMENT"]}
