import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from tradingview_scraper.utils.audit import AuditLedger

logger = logging.getLogger(__name__)


class ModelRegistry:
    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.ledger = AuditLedger(run_dir)

    def register_model(self, run_id: str, metrics: Dict[str, Any], tags: List[str]):
        """
        Appends a 'model_registered' event to the ledger.
        """
        record = {
            "type": "model_registered",
            "run_id": run_id,
            "metrics": metrics,
            "tags": tags,
        }
        # Use the private _append method to maintain the chain
        self.ledger._append(record)
        logger.info(f"Registered model {run_id} with metrics: {metrics} and tags: {tags}")

    def list_models(self, min_sharpe: float = 0.0) -> List[Dict[str, Any]]:
        """
        Queries the audit ledger for registered models meeting criteria.
        """
        models = []
        if not self.ledger.path.exists():
            return models

        try:
            with open(self.ledger.path, "r") as f:
                for line in f:
                    try:
                        record = json.loads(line)
                        if record.get("type") == "model_registered":
                            metrics = record.get("metrics", {})
                            # Check for 'sharpe' or 'Sharpe'
                            sharpe = metrics.get("sharpe", metrics.get("Sharpe", -999.0))
                            if float(sharpe) >= min_sharpe:
                                models.append(record)
                    except (json.JSONDecodeError, ValueError):
                        continue
        except Exception as e:
            logger.error(f"Failed to list models: {e}")

        return models
