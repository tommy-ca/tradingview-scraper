---
title: Run-Scoped Metadata Ingestion
type: feat
date: 2026-01-29
status: deepened
---

# Run-Scoped Metadata Ingestion

## Enhancement Summary
**Deepened on:** 2026-01-29
**Research Agents:** Security Sentinel, Data Integrity Guardian, Performance Oracle, Kieran Python Reviewer, Research/Explore.

### Key Improvements
1.  **Security Hardening**: Added input validation to prevent path traversal attacks via `--candidates-file`.
2.  **Data Integrity**: Introduced "Atomic Write" and "File Locking" patterns to prevent catalog corruption during concurrent runs.
3.  **Robustness**: Replaced fragile "guess-by-first-element" JSON parsing with a robust, type-safe iteration approach.
4.  **Modern Python**: Standardized on `pathlib` and typed interfaces.

---

## Overview

Optimize the `scripts/build_metadata_catalog.py` utility to support **Run-Scoped Ingestion**. Instead of refreshing the entire 1130+ symbol universe by default, the script will accept a target list of candidates (from the current DataOps run) and only fetch/update metadata for those specific symbols. Additionally, we will introduce concurrency controls to ensure friendly behavior toward public endpoints.

## Problem Statement

Currently, `make meta-refresh` (or equivalent) calls `scripts/build_metadata_catalog.py --from-catalog`, which re-fetches metadata for **all** known symbols. This is:
1.  **Slow**: Fetches 1130+ symbols even if we only care about 20 for the current run.
2.  **Risky**: High concurrency (default 10 workers) triggers 429/403 errors from TradingView.
3.  **Wasteful**: Updates metadata that hasn't changed or isn't needed.

## Proposed Solution

1.  **Targeted Input**: Add `--candidates-file` argument to `scripts/build_metadata_catalog.py` to load symbols from a JSON file (e.g., `portfolio_candidates.json`).
2.  **Concurrency Control**: Add `--workers` argument to limit parallel requests (defaulting to a safe low number like 3).
3.  **Incremental Update**: Ensure the script merges the new metadata with the existing `symbols.parquet` catalog using an **Upsert** pattern.
4.  **Workflow Integration**: Update `Makefile` to use these flags in the `meta-ingest` target.

## Technical Considerations

### 1. Robust JSON Parsing (Polymorphism)
The script must handle both `["BTCUSDT"]` and `[{"symbol": "BTCUSDT"}]` formats without fragile guessing.

**Research Insight (Implementation Pattern):**
```python
def parse_candidates(data: list[Any]) -> list[str]:
    symbols = set()
    for item in data:
        if isinstance(item, str):
            symbols.add(item)
        elif isinstance(item, dict) and "symbol" in item:
            symbols.add(str(item["symbol"]))
    return sorted(symbols)
```

### 2. Security & Input Validation
**Risk**: Path Traversal via `--candidates-file`.
**Mitigation**: Enforce that the file resides within the project root.

**Research Insight (Security Pattern):**
```python
from pathlib import Path

def validate_path(path_str: str) -> Path:
    path = Path(path_str).resolve()
    root = Path.cwd().resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"Security Violation: Path {path} is outside project root")
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return path
```

### 3. Data Integrity: Atomic Writes & Locking
**Risk**: Concurrent writes or crashes corrupting `symbols.parquet`.
**Mitigation**: Use "Write-to-Temp-and-Rename" pattern and File Locking.

**Research Insight (Atomic Write Pattern):**
```python
import uuid
import os

def atomic_write_parquet(df: pd.DataFrame, filepath: Path):
    """Safe write using temp file and atomic rename."""
    temp_path = filepath.with_suffix(f".tmp.{uuid.uuid4().hex}.parquet")
    try:
        df.to_parquet(temp_path)
        os.replace(temp_path, filepath) # Atomic on POSIX
    except Exception as e:
        if temp_path.exists(): temp_path.unlink()
        raise e
```

## Acceptance Criteria

- [x] `scripts/build_metadata_catalog.py` accepts `--candidates-file <path>`.
- [x] `scripts/build_metadata_catalog.py` accepts `--workers <int>` (default: 3).
- [x] **Security**: Input file path is validated against project root.
- [x] **Robustness**: Script parses mixed-format JSON correctly without crashing.
- [x] **Integrity**: Updates are written atomically (temp -> rename).
- [x] `make meta-ingest` uses the new flags with the current run's candidate file.

## Success Metrics

- Metadata refresh for a typical run (50 candidates) takes < 10 seconds.
- No 429 errors observed during standard pipeline execution.
- No data corruption observed during concurrent executions (simulated).

## Implementation Plan

### Phase 1: Script Refactoring & Logic
1.  **Refactor**: Extract logic from `main()` into `MetadataIngestionJob` class.
2.  **Input Handling**: Implement `validate_path` and `parse_candidates` helpers.
3.  **Merge Logic**: Implement `upsert_monolithic` method:
    - Load existing parquet.
    - `pd.concat([existing, new])`.
    - `drop_duplicates(subset=['symbol'], keep='last')`.
4.  **Atomic Persistence**: Implement `atomic_write_parquet`.

### Phase 2: CLI & Integration
1.  **Update CLI**: Add `argparse` flags for `--candidates-file` and `--workers`.
2.  **Makefile**: Update `meta-ingest` target to pass `CANDIDATES_FILE` variable.

## References
- **Parquet Safety**: `docs/solutions/data-engineering/atomic-parquet-writes.md` (To be created)
- **API Patterns**: `docs/solutions/python/friendly-api-fetcher.md` (To be created)
