---
status: complete
priority: p1
issue_id: "105"
tags: [code-review, audit, performance, security]
dependencies: []
---

# Fix AuditLedger append performance and concurrency

## Problem Statement

`AuditLedger._append()` currently refreshes `last_hash` by reading the entire ledger file on every append and does not lock writes.

This creates:
- severe performance degradation as `audit.jsonl` grows (O(N^2) behavior)
- integrity risks under concurrent writers (hash chain can fork; JSONL can corrupt)

## Findings

- `tradingview_scraper/utils/audit.py:126` calls `_initialize_chain()` per append.
- `_initialize_chain()` uses `readlines()` and loads the last line each time.
- No cross-process lock exists around “read last hash + append”.

## Proposed Solutions

### Option 1: Add a ledger lock + tail-read last hash (Recommended)

**Approach:**
- Use an OS-level lock (fcntl/flock) in `AuditLedger._append`.
- Replace full-file `readlines()` with an EOF tail-scan to find the last complete JSON line.

**Pros:**
- Preserves cryptographic chain under concurrency
- Removes O(N) per append overhead

**Cons:**
- More complex file I/O

**Effort:** Medium

**Risk:** Medium

---

### Option 2: Enforce single-writer ownership

**Approach:**
- Architecturally guarantee only the orchestrator writes to `audit.jsonl`.

**Pros:**
- Simplest runtime model

**Cons:**
- Hard to guarantee long-term

**Effort:** Medium

**Risk:** Medium

## Recommended Action

Implement an OS-level exclusive lock and tail-scan for the last hash.

## Technical Details

**Affected files:**
- `tradingview_scraper/utils/audit.py`

## Acceptance Criteria

- [x] Appending N records does not do O(N) file reads per append
- [x] Concurrent append does not fork the hash chain
- [x] Ledger remains valid JSONL with complete lines (no interleaving)
- [x] Add a test that verifies `prev_hash` matches previous `hash` under multi-process appends

## Work Log

### 2026-02-11 - Review Finding

**By:** Claude Code

**Actions:**
- Observed `uv run pytest` suite slowdown/timeouts due to import errors; performance review flagged ledger append as systemic bottleneck

### 2026-02-12 - Implementation

**By:** OpenCode

**Actions:**
- Replaced full-file `readlines()` with tail-scan hash recovery.
- Added cross-process exclusive locking for the append critical section.
- Added tests for multi-process chain integrity and a functional perf guard.
