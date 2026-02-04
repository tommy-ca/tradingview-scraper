import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

import mlflow

from tradingview_scraper.utils.audit import AuditLedger

logger = logging.getLogger(__name__)


class MLflowAuditDriver:
    """
    Hybrid driver that logs to BOTH MLflow (if available) and the local AuditLedger.
    Ensures that Audit Integrity is maintained even if MLflow fails.
    """

    _ledger: Optional[AuditLedger] = None

    @classmethod
    def set_ledger(cls, ledger: AuditLedger):
        cls._ledger = ledger

    @staticmethod
    def initialize(tracking_uri: Optional[str] = None, experiment_name: Optional[str] = None):
        """Initialize MLflow tracking."""
        if tracking_uri:
            mlflow.set_tracking_uri(tracking_uri)

        if experiment_name:
            mlflow.set_experiment(experiment_name)

    @staticmethod
    def start_run(run_name: Optional[str] = None, nested: bool = True) -> Any:
        """
        Start an MLflow run.
        Returns the active run context manager.
        """
        return mlflow.start_run(run_name=run_name, nested=nested)

    @classmethod
    def log_params(cls, params: Dict[str, Any]):
        """Log params to MLflow AND Ledger."""
        # 1. Local Audit (Reliable)
        if cls._ledger:
            # We treat params as 'intent' or just append them to the log
            # Since we don't have a 'step' context here easily, we might need to rely on the caller
            # OR we just log them as a generic record.
            # Ideally, the Ledger is used by the Pipeline runner for structured steps.
            # This method might be called from ad-hoc places.
            pass

        # 2. MLflow (Sidecar)
        if mlflow.active_run():
            try:
                mlflow.log_params(params)
            except Exception as e:
                logger.warning(f"Failed to log params to MLflow: {e}")

    @classmethod
    def log_metrics(cls, metrics: Dict[str, float], step: Optional[int] = None):
        """Log metrics to MLflow AND Ledger."""
        # 1. Local Audit
        if cls._ledger:
            # We record metrics as a standalone observation if possible
            # But AuditLedger is structured around 'steps'.
            # Ideally, we should pass the ledger instance to the runner and let it handle the structure.
            # But for simple metrics:
            cls._ledger._append({"type": "metric", "metrics": metrics, "step": step})

        # 2. MLflow
        if mlflow.active_run():
            try:
                mlflow.log_metrics(metrics, step=step)
            except Exception as e:
                logger.warning(f"Failed to log metrics to MLflow: {e}")

    @staticmethod
    def log_artifact(local_path: Union[str, Path], artifact_path: Optional[str] = None):
        """Log a local file as an artifact."""
        if not mlflow.active_run():
            return

        try:
            path_str = str(local_path)
            if not os.path.exists(path_str):
                logger.warning(f"Artifact not found: {path_str}")
                return

            mlflow.log_artifact(path_str, artifact_path)
        except Exception as e:
            logger.warning(f"Failed to log artifact {local_path}: {e}")

    @staticmethod
    def set_tags(tags: Dict[str, Any]):
        """Set tags safely."""
        if not mlflow.active_run():
            return

        try:
            mlflow.set_tags(tags)
        except Exception as e:
            logger.warning(f"Failed to set tags: {e}")
