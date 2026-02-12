import hashlib
import json
import multiprocessing as mp
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from tradingview_scraper.utils.audit import AuditLedger, verify_audit_chain


def _concurrent_append_worker(run_dir: str, n: int, worker_id: int) -> None:
    ledger = AuditLedger(Path(run_dir))
    for i in range(n):
        ledger.record_intent(
            step="concurrent",
            params={"i": i, "worker": worker_id},
            input_hashes={"worker": str(worker_id)},
            context={"worker": worker_id, "i": i},
        )


@dataclass
class _Counter:
    read_bytes: int = 0


def test_audit_ledger_chaining(tmp_path):
    """Test that entries are correctly chained and verifiable."""
    ledger = AuditLedger(tmp_path)

    # Record genesis
    ledger.record_genesis("run-123", "production", "manifest-sha")

    # Record some actions
    ledger.record_intent("step1", {"p": 1}, {"in": "h1"})
    ledger.record_outcome("step1", "success", {"out": "h2"}, {"m": 0.5})

    audit_file = tmp_path / "audit.jsonl"
    assert audit_file.exists()

    # Verify integrity using the production tool
    assert verify_audit_chain(audit_file) is True


def test_audit_ledger_tamper_detection(tmp_path):
    """Test that tampering with the ledger breaks the chain."""
    ledger = AuditLedger(tmp_path)
    ledger.record_genesis("run-123", "production", "manifest-sha")
    ledger.record_intent("step1", {"p": 1}, {"in": "h1"})

    audit_file = tmp_path / "audit.jsonl"

    # Read and tamper
    with open(audit_file, "r") as f:
        lines = f.readlines()

    # Modify a value in the first record (genesis)
    record = json.loads(lines[0])
    record["run_id"] = "TAMPERED"
    lines[0] = json.dumps(record) + "\n"

    with open(audit_file, "w") as f:
        f.writelines(lines)

    # Verification should now fail
    assert verify_audit_chain(audit_file) is False


def test_audit_ledger_resume(tmp_path):
    """Test that ledger can resume from an existing file and maintain the chain."""
    ledger = AuditLedger(tmp_path)
    ledger.record_genesis("run-1", "prod", "h1")
    first_hash = ledger.last_hash

    # Create a new ledger instance pointing to same dir
    ledger2 = AuditLedger(tmp_path)
    assert ledger2.last_hash == first_hash

    ledger2.record_intent("step2", {}, {})
    assert verify_audit_chain(tmp_path / "audit.jsonl") is True


def test_audit_ledger_concurrent_multi_process_appends_do_not_fork(tmp_path):
    ledger = AuditLedger(tmp_path)
    ledger.record_genesis("run-1", "prod", "h1")

    n_procs = 6
    n_each = 50
    ctx = mp.get_context("spawn")
    procs = [ctx.Process(target=_concurrent_append_worker, args=(str(tmp_path), n_each, wid)) for wid in range(n_procs)]

    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=60)

    assert all(p.exitcode == 0 for p in procs)

    audit_file = tmp_path / "audit.jsonl"
    lines = audit_file.read_text().splitlines()
    assert len(lines) == 1 + (n_procs * n_each)
    assert verify_audit_chain(audit_file) is True


def test_audit_ledger_append_tail_read_is_not_full_scan(tmp_path):
    """Functional perf guard: _append must not do full-file readlines() per append."""
    audit_file = tmp_path / "audit.jsonl"

    # Seed a moderately large ledger quickly (no AuditLedger writes / fsync).
    prev = "0" * 64
    with open(audit_file, "wb") as f:
        for i in range(5000):
            record = {"type": "seed", "i": i, "ts": "2026-01-01T00:00:00", "prev_hash": prev}
            record_json = json.dumps(record, sort_keys=True)
            h = hashlib.sha256(record_json.encode("utf-8")).hexdigest()
            record["hash"] = h
            f.write((json.dumps(record) + "\n").encode("utf-8"))
            prev = h

    counter = _Counter()
    real_open = open

    class CountingFile:
        def __init__(self, inner):
            self._inner = inner

        def __enter__(self):
            self._inner.__enter__()
            return self

        def __exit__(self, exc_type, exc, tb):
            return self._inner.__exit__(exc_type, exc, tb)

        def read(self, n=-1):
            data = self._inner.read(n)
            try:
                counter.read_bytes += len(data)
            except Exception:
                pass
            return data

        def readlines(self, *args, **kwargs):
            raise AssertionError("AuditLedger must not call readlines() during append")

        def __getattr__(self, name):
            return getattr(self._inner, name)

    def open_side_effect(file, mode="r", *args, **kwargs):
        f = real_open(file, mode, *args, **kwargs)
        try:
            if Path(file) == audit_file and "b" in mode and ("a" in mode or "+" in mode):
                return CountingFile(f)
        except Exception:
            pass
        return f

    ledger = AuditLedger(tmp_path)

    with patch("builtins.open", side_effect=open_side_effect):
        for i in range(200):
            ledger.record_intent("perf", {"i": i}, {"in": "h"})

    # Tail-scan should read O(1) per append; guard against accidental full scans.
    assert counter.read_bytes < 5_000_000
    assert verify_audit_chain(audit_file) is True
