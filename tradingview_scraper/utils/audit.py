from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


def get_df_hash(df: pd.DataFrame | pd.Series) -> str:
    """
    Computes a stable, deterministic SHA-256 hash of a DataFrame or Series.
    Ignores memory addresses and non-essential metadata.
    Forces indices to naive UTC string representations for cross-environment parity.
    """
    if df.empty:
        return hashlib.sha256(b"empty").hexdigest()

    try:
        obj = df.copy()

        idx = obj.index
        if isinstance(idx, pd.DatetimeIndex) and idx.tz is not None:
            obj.index = idx.tz_convert(None)

        if isinstance(obj, pd.DataFrame):
            try:
                obj = obj.sort_index().sort_index(axis=1)
            except Exception:
                obj = obj.reindex(sorted(obj.index, key=str)).reindex(columns=sorted(obj.columns, key=str))
        else:
            try:
                obj = obj.sort_index()
            except Exception:
                obj = obj.reindex(sorted(obj.index, key=str))

        # 1. Standardize Index
        idx = obj.index
        if isinstance(idx, pd.DatetimeIndex):
            # Use ISO format for maximum string stability
            idx_list = idx.strftime("%Y-%m-%dT%H:%M:%S").tolist()
        else:
            idx_list = [str(x) for x in idx]

        idx_str = "|".join(idx_list)

        # 2. Standardize Columns (if DataFrame)
        cols_str = ""
        if isinstance(obj, pd.DataFrame):
            cols_str = "|".join([str(c) for c in obj.columns])

        # 3. Standardize Data
        # We use a high-precision rounded string representation for floats to avoid
        # float64 byte variations across different architectures/OS.
        # 8 decimals is enough for financial returns.
        data_flat = obj.to_numpy().flatten()
        data_list = []
        for x in data_flat:
            try:
                # If it looks like a number, format it specifically
                if pd.api.types.is_number(x) and not isinstance(x, bool):
                    # Use a very robust way to get a float string
                    try:
                        val = float(str(x))
                        data_list.append(f"{val:.8f}")
                    except (ValueError, TypeError):
                        data_list.append(str(x))
                else:
                    data_list.append(str(x))
            except Exception:
                data_list.append(str(x))
        data_str = "|".join(data_list)

        # 4. Final Fingerprint
        combined = f"idx:{idx_str};cols:{cols_str};data:{data_str}"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()
    except Exception as e:
        logger.warning(f"Fallback hashing for object type {type(df)}: {e}")
        return hashlib.sha256(str(df.shape).encode()).hexdigest()


def get_env_hash() -> str:
    """Generates a hash of the current environment state (uv.lock, pyproject.toml)."""
    env_str = ""
    for filename in ["uv.lock", "pyproject.toml"]:
        p = Path(filename)
        if p.exists():
            env_str += p.read_text()

    # Add python version
    env_str += sys.version
    return hashlib.sha256(env_str.encode()).hexdigest()


class AuditLedger:
    """
    Append-only, cryptographically chained decision ledger.
    Implements the WAL (Write-Ahead Logging) principle.
    """

    def __init__(self, run_dir: Path):
        self.path = run_dir / "audit.jsonl"
        self.last_hash: str | None = None
        self._initialize_chain()

    @staticmethod
    def _lock_exclusive(fd: int) -> None:
        """Cross-process exclusive lock on a file descriptor."""
        if os.name == "nt":
            # Best-effort no-op on Windows; repository primarily targets Linux.
            return

        import fcntl

        fcntl.flock(fd, fcntl.LOCK_EX)

    @staticmethod
    def _unlock(fd: int) -> None:
        if os.name == "nt":
            return

        import fcntl

        fcntl.flock(fd, fcntl.LOCK_UN)

    @staticmethod
    def _read_last_hash_from_file(f) -> str | None:
        """Reads the last valid JSONL record hash without loading the full file."""
        try:
            f.seek(0, os.SEEK_END)
            end = f.tell()
            if end == 0:
                return None

            block_size = 4096
            pos = end
            data = b""

            # Collect enough bytes from the tail to include the last full line.
            # This scales with last-line length, not file length.
            while pos > 0 and data.count(b"\n") < 2:
                read_size = block_size if pos >= block_size else pos
                pos -= read_size
                f.seek(pos, os.SEEK_SET)
                chunk = f.read(read_size)
                if not chunk:
                    break
                data = chunk + data
                if len(data) > 1024 * 1024:
                    # Defensive cap: we should never need to read more than
                    # a reasonable single JSON line.
                    break

            # Remove trailing newlines and try parsing from the end.
            data = data.rstrip(b"\n")
            if not data:
                return None

            for raw_line in reversed(data.splitlines()):
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    obj = json.loads(raw_line.decode("utf-8"))
                except Exception:
                    continue
                h = obj.get("hash")
                if isinstance(h, str) and len(h) == 64:
                    return h
            return None
        except Exception as e:
            logger.error(f"Failed to tail-read audit chain: {e}")
            return None

    def _initialize_chain(self):
        """Discovers the last hash if the file already exists (for resumed runs)."""
        if not self.path.exists():
            return

        try:
            with open(self.path, "rb") as f:
                self.last_hash = self._read_last_hash_from_file(f)
        except Exception as e:
            logger.error(f"Failed to recover audit chain: {e}")

    def _append(self, record: dict[str, Any]):
        """Calculates hash, chains to previous, and appends to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # One critical section: read tail (prev hash) + append.
        # This prevents hash-chain forks and JSONL interleaving.
        with open(self.path, "a+b") as f:
            fd = f.fileno()
            self._lock_exclusive(fd)
            try:
                prev_hash = self._read_last_hash_from_file(f) or "0" * 64

                ts = datetime.now().isoformat()
                record["ts"] = ts
                record["prev_hash"] = prev_hash

                # Calculate signature of this record (deterministic ordering)
                record_json = json.dumps(record, sort_keys=True)
                current_hash = hashlib.sha256(record_json.encode("utf-8")).hexdigest()
                record["hash"] = current_hash

                line = (json.dumps(record) + "\n").encode("utf-8")
                f.write(line)
                f.flush()
                os.fsync(fd)

                self.last_hash = current_hash
            finally:
                self._unlock(fd)

    def record_genesis(self, run_id: str, profile: str, manifest_hash: str, config: dict[str, Any] | None = None):
        """Creates the Genesis Block for a new run."""
        git_hash = "unknown"
        try:
            import subprocess

            git_hash = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("ascii").strip()
        except Exception:
            pass

        record = {
            "type": "genesis",
            "run_id": run_id,
            "profile": profile,
            "env": {
                "python": sys.version,
                "manifest_hash": manifest_hash,
                "env_hash": get_env_hash(),
                "git_hash": git_hash,
            },
        }
        if config:
            record["config"] = config
        self._append(record)

    def record_intent(
        self,
        step: str,
        params: dict[str, Any],
        input_hashes: dict[str, str],
        data: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ):
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
        if data:
            record["data"] = data
        if context:
            record["context"] = context
        self._append(record)

    def record_outcome(
        self,
        step: str,
        status: str,
        output_hashes: dict[str, str],
        metrics: dict[str, Any],
        data: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ):
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
        if data:
            record["data"] = data
        if context:
            record["context"] = context
        self._append(record)


def verify_audit_chain(path: Path) -> bool:
    """Verifies that the audit.jsonl file is a valid, chained ledger."""
    try:
        prev = "0" * 64
        with open(path, "rb") as f:
            for raw_line in f:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                obj = json.loads(raw_line.decode("utf-8"))

                if obj.get("prev_hash") != prev:
                    return False

                recorded_hash = obj.get("hash")
                if not isinstance(recorded_hash, str) or len(recorded_hash) != 64:
                    return False

                # Recompute the hash on the record without its own hash field.
                unsigned = dict(obj)
                unsigned.pop("hash", None)
                record_json = json.dumps(unsigned, sort_keys=True)
                computed = hashlib.sha256(record_json.encode("utf-8")).hexdigest()
                if computed != recorded_hash:
                    return False

                prev = recorded_hash
        return True
    except Exception:
        return False
