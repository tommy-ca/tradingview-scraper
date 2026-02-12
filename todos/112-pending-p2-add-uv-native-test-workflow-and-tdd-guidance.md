---
status: pending
priority: p2
issue_id: "112"
tags: [code-review, devex, testing]
dependencies: []
---

# Add uv-native test workflow and TDD guidance

## Problem Statement

The repository should support a spec-driven development workflow where targeted tests can be run reliably using `uv` native commands.

Currently, running the full suite fails due to unrelated import issues; without a documented “focused test workflow”, TDD for new modules is noisy.

## Findings

- `uv` is installed and usable.
- `uv run --extra dev pytest -q tests/test_daily_risk_budget_slices.py` passes.
- `uv run --extra dev pytest -q` currently fails due to unrelated missing imports and optional deps (eg Prefect) across the test suite.

## Proposed Solutions

### Option 1: Add focused test targets + document the workflow (Recommended)

**Approach:**
- Add a `make test-risk-budget` target:
  - `uv run --extra dev pytest -q tests/test_daily_risk_budget_slices.py`
- Add a `make test-unit` target that excludes integration tests and optional deps, if feasible.
- Add a short `docs/dev/testing.md` describing how to do TDD with focused test files.

**Pros:**
- Enables TDD even when suite has unrelated failures

**Cons:**
- Requires choosing a standard for “unit vs integration” markers

**Effort:** Small/Medium

**Risk:** Low

---

### Option 2: Fix entire suite imports

**Approach:**
- Refactor tests to avoid importing from `scripts/*` and ensure optional deps are optional.

**Pros:**
- Full suite becomes reliable

**Cons:**
- Potentially large scope unrelated to this feature

**Effort:** Large

**Risk:** Medium

## Recommended Action

To be filled during triage.

## Technical Details

**Affected files (likely):**
- `Makefile`
- `docs/dev/testing.md`
- `pyproject.toml` (optional: pytest config/markers)

## Acceptance Criteria

- [ ] A documented uv-native command exists for running targeted tests
- [ ] At least one Make target exists for feature-focused tests
- [ ] TDD workflow is documented and does not require global python or pip

## Work Log

### 2026-02-11 - Review Finding

**By:** Claude Code

**Actions:**
- Ran targeted tests using uv; observed full suite failing due to unrelated import issues
