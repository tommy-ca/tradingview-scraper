import mlflow
from pathlib import Path
from typing import Dict, Any, Optional, Union


class MLflowTracker:
    """
    View-Only MLflow tracker for observability.

    This class is designed to be a passive logger ("View-Only Role").
    It does not manage the lifecycle of the application or control execution flow.
    It assumes an experiment context or creates a run if none exists, but avoids
    creating nested runs for metric groups.
    """

    def __init__(self, experiment_name: Optional[str] = None):
        """
        Initialize the tracker.

        Args:
            experiment_name: Optional name of the experiment. If provided,
                           sets the experiment context.
        """
        if experiment_name:
            mlflow.set_experiment(experiment_name)

    def _flatten_dict(self, d: Dict[str, Any], parent_key: str = "", sep: str = ".") -> Dict[str, Any]:
        """Recursively flatten a nested dictionary."""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)

    def log_metrics(self, metrics: Dict[str, Any], tags: Optional[Dict[str, str]] = None) -> None:
        """
        Log metrics to MLflow.

        - Flattens nested metrics dictionaries.
        - Does NOT create nested runs (logs everything to current/active run).

        Args:
            metrics: Dictionary of metrics (can be nested).
            tags: Optional dictionary of tags to apply to the run.
        """
        flat_metrics = self._flatten_dict(metrics)

        # Ensure values are float/numeric for log_metrics
        numeric_metrics = {}
        for k, v in flat_metrics.items():
            try:
                numeric_metrics[k] = float(v)
            except (ValueError, TypeError):
                # Skip non-numeric metrics or log as params?
                # Standard MLflow metrics must be numeric.
                continue

        if tags:
            mlflow.set_tags(tags)

        if numeric_metrics:
            mlflow.log_metrics(numeric_metrics)

    def log_params(self, params: Dict[str, Any]) -> None:
        """
        Log parameters to MLflow.

        Args:
            params: Dictionary of parameters (can be nested, will be flattened).
        """
        flat_params = self._flatten_dict(params)
        mlflow.log_params(flat_params)

    def log_artifact(self, path: Union[str, Path]) -> None:
        """
        Log a local file as an artifact.

        Security Hardening:
        - Vetoes pickle files (.pkl, .pickle).
        - ONLY allows .parquet and .json files.

        Args:
            path: Path to the file to log.

        Raises:
            ValueError: If file type is not allowed or is a pickle file.
            FileNotFoundError: If the file does not exist.
        """
        file_path = Path(path)

        if not file_path.exists():
            raise FileNotFoundError(f"Artifact not found: {path}")

        # Security Hardening
        suffix = file_path.suffix.lower()

        # Explicit Veto
        if suffix in [".pkl", ".pickle"]:
            raise ValueError(f"Security Alert: Attempted to log unsafe pickle artifact: {path}")

        # Explicit Allowlist
        allowed_extensions = [".parquet", ".json"]
        if suffix not in allowed_extensions:
            raise ValueError(f"Security Alert: Artifact type {suffix} not allowed. Allowed types: {allowed_extensions}")

        mlflow.log_artifact(str(file_path))
