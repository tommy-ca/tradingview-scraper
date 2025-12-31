from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, cast

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def get_df_hash(df: pd.DataFrame) -> str:
    """
    Computes a stable, deterministic SHA-256 hash of a DataFrame.
    Ignores memory addresses and non-essential metadata.
    """
    if df.empty:
        return hashlib.sha256(b"empty").hexdigest()

    # Convert to values-only representation for hashing
    # Using JSON for stability and ease of inspection for small DFs,
    # but for large return matrices, we use the underlying values.
    try:
        # Standardize index and columns
        df_stable = df.sort_index(axis=0).sort_index(axis=1)
        # Use values + index + columns to ensure structure is preserved
        combined = str(df_stable.values.tobytes()) + str(np.asarray(df_stable.index).tobytes()) + str(np.asarray(df_stable.columns).tobytes())
        return hashlib.sha256(combined.encode()).hexdigest()
    except Exception as e:
        logger.warning(f"Fallback hashing for DataFrame: {e}")
        return hashlib.sha256(str(df.shape).encode()).hexdigest()


class AuditLedger:
    """
    Append-only, cryptographically chained decision ledger.
    Implements the WAL (Write-Ahead Logging) principle.
    """

    def __init__(self, run_dir: Path):
        self.path = run_dir / "audit.jsonl"
        self.last_hash: Optional[str] = None
        self._initialize_chain()

    def _initialize_chain(self):
        """Discovers the last hash if the file already exists (for resumed runs)."""
        if not self.path.exists():
            return

        try:
            with open(self.path, "r") as f:
                lines = f.readlines()
                if lines:
                    last_line = json.loads(lines[-1])
                    self.last_hash = last_line.get("hash")
        except Exception as e:
            logger.error(f"Failed to recover audit chain: {e}")

    def _append(self, record: Dict[str, Any]):
        """Calculates hash, chains to previous, and appends to disk."""
        ts = datetime.now().isoformat()
        record["ts"] = ts
        record["prev_hash"] = self.last_hash or "0" * 64

        # Calculate signature of this record
        # We sort keys for determinism
        record_json = json.dumps(record, sort_keys=True)
        current_hash = hashlib.sha256(record_json.encode()).hexdigest()
        record["hash"] = current_hash

        with open(self.path, "a") as f:
            f.write(json.dumps(record) + "\n")

        self.last_hash = current_hash

    def record_genesis(self, run_id: str, profile: str, manifest_hash: str):
        """Creates the Genesis Block for a new run."""
        record = {
            "type": "genesis",
            "run_id": run_id,
            "profile": profile,
            "env": {
                "python": sys.version,
                "manifest_hash": manifest_hash,
            },
        }
        self._append(record)

    def record_intent(self, step: str, params: Dict[str, Any], input_hashes: Dict[str, str]):
        """Logs an intent to perform a pipeline action."""
        record = {
            "type": "action",
            "status": "intent",
            "step": step,
            "intent": {
                "params": params,
                "input_hashes": input_hashes,
            },
        }
        self._append(record)

    def record_outcome(self, step: str, status: str, output_hashes: Dict[str, str], metrics: Dict[str, Any]):
        """Logs the outcome of a pipeline action."""
        record = {
            "type": "action",
            "status": status,
            "step": step,
            "outcome": {
                "output_hashes": output_hashes,
                "metrics": metrics,
            },
        }
        self._append(record)


import sys  # Needed for sys.version
