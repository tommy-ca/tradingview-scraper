import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Optional

import ray

from tradingview_scraper.settings import get_settings
from tradingview_scraper.telemetry.context import extract_trace_context
from tradingview_scraper.telemetry.provider import TelemetryProvider
from tradingview_scraper.telemetry.tracing import trace_span

logger = logging.getLogger(__name__)


class SleeveActorImpl:
    """
    Stateful Ray Actor Implementation that executes a strategy sleeve's production pipeline.
    Handles process isolation, environment propagation, and artifact export.
    """

    def __init__(self, host_cwd: str, env_vars: Dict[str, str], trace_context: Optional[Dict[str, str]] = None):
        self.host_cwd = host_cwd

        # 1. Environment Setup
        if "VIRTUAL_ENV" in env_vars:
            del env_vars["VIRTUAL_ENV"]

        # Enforce Production Isolation Defaults
        env_vars["TV_STRICT_HEALTH"] = "1"
        env_vars["TV_STRICT_ISOLATION"] = "1"

        os.environ.update(env_vars)

        # 2. Telemetry Initialization (Distributed Trace Linkage)
        self.provider = TelemetryProvider()
        self.provider.initialize(service_name="sleeve-actor")
        self.trace_context = trace_context

        # 3. Settings Initialization
        get_settings.cache_clear()
        self.settings = get_settings()

        # 4. Workspace Isolation (Mixed Symlink Strategy)
        self._setup_workspace()

    def _setup_workspace(self):

    def _setup_workspace(self):
        """
        Setup the 'data' directory structure in the worker.
        - data/lakehouse: SYMLINK to host (Read-only shared input)
        - data/export: SYMLINK to host (Shared scanner input)
        - data/artifacts: LOCAL (Isolated output)
        - data/logs: LOCAL (Isolated logs)
        """
        data_root = self.settings.data_dir
        data_root.mkdir(parents=True, exist_ok=True)

        def link_subdir(subdir_attr: str):
            target_path = getattr(self.settings, subdir_attr)
            host_path = Path(self.host_cwd) / target_path

            if target_path.exists():
                if target_path.is_symlink():
                    return
                if target_path.is_dir() and not any(target_path.iterdir()):
                    target_path.rmdir()
                else:
                    logger.warning(f"Local {target_path} exists and is not empty. Skipping link.")
                    return

            if host_path.exists():
                os.symlink(host_path, target_path)
                logger.info(f"🔗 Linked {target_path} -> {host_path}")

        # Symlink Shared Inputs
        link_subdir("lakehouse_dir")
        link_subdir("export_dir")

        # Symlink .venv for uv execution
        if not os.path.exists(".venv"):
            host_venv = os.path.join(self.host_cwd, ".venv")
            if os.path.exists(host_venv):
                os.symlink(host_venv, ".venv")

        # Local Outputs
        self.settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.settings.logs_dir.mkdir(parents=True, exist_ok=True)

    @trace_span("sleeve_actor.run_pipeline")
    def run_pipeline(self, profile: str, run_id: str) -> Dict[str, Any]:
        """
        Executes the ProductionPipeline for the given profile.
        Exports resulting artifacts back to the host filesystem.
        """
        start_time = time.time()
        logger.info(f"🚀 [Ray] Starting sleeve production: {profile} (Run: {run_id})")

        status = "success"
        error_msg = None

        # Extract parent trace context if available
        context = extract_trace_context(self.trace_context) if self.trace_context else None

        from tradingview_scraper.telemetry.tracing import get_tracer

        tracer = get_tracer()
        with tracer.start_as_current_span("run_production_pipeline", context=context):
            try:
                from scripts.run_production_pipeline import ProductionPipeline

                # The pipeline class handles its own run_id directory preparation
                pipeline = ProductionPipeline(profile=profile, run_id=run_id)
                pipeline.execute()

            except Exception as e:
                logger.error(f"❌ [Ray] Pipeline failed for {profile}: {e}", exc_info=True)
                status = "error"
                error_msg = str(e)
            finally:
                self._export_artifacts(run_id)

        duration = time.time() - start_time
        return {"profile": profile, "run_id": run_id, "status": status, "duration": duration, "error": error_msg, "node": ray.util.get_node_ip_address()}

    def _export_artifacts(self, run_id: str):
        """Copies local artifacts back to the host filesystem."""
        local_run_dir = self.settings.summaries_runs_dir / run_id
        host_run_dir = Path(self.host_cwd) / self.settings.summaries_runs_dir / run_id

        if local_run_dir.exists():
            logger.info(f"📦 Exporting artifacts for {run_id}")
            host_run_dir.parent.mkdir(parents=True, exist_ok=True)

            if host_run_dir.exists():
                shutil.rmtree(host_run_dir)

            shutil.copytree(local_run_dir, host_run_dir)
            logger.info(f"✅ Artifacts exported to host: {host_run_dir}")
        else:
            logger.warning(f"⚠️ No artifacts found at {local_run_dir} to export.")


# Define the Ray Actor with aggressive memory capping for constrained local environments
SleeveActor = ray.remote(num_cpus=1, memory=0.5 * 1024 * 1024 * 1024)(SleeveActorImpl)
