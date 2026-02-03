---
status: complete
priority: p2
issue_id: "009"
tags: [quality, technical-debt]
dependencies: []
---

# Legacy Type Hints Update (Python 3.10+)

The codebase still uses legacy `typing` module imports and syntax (e.g., `List`, `Dict`, `Optional`, `Union`) instead of the modern Python 3.10+ PEP 585 and PEP 604 syntax.

## Problem Statement

- Legacy typing syntax is more verbose and requires extra imports from the `typing` module.
- Modern syntax (e.g., `list[str]`, `str | None`) is cleaner, more readable, and aligns with current Python best practices.
- Mixing legacy and modern syntax creates inconsistency across the codebase.

## Findings

- **File**: `scripts/backtest_engine.py:6` - Uses `Dict`, `List`, `Optional`.
- **File**: `tradingview_scraper/utils/predictability.py:3` - Uses `Dict`, `Optional`.
- **File**: `scripts/services/ingest_data.py:7` - Uses `Any`, `Dict`, `List`.
- Many other files in `tradingview_scraper/` likely contain legacy hints.
- LSP errors frequently highlight issues with `Optional` and `Union` types that could be clarified with modern syntax.

## Proposed Solutions

### Option 1: Incremental Update
**Approach:** Update type hints in files as they are modified for other tasks.

**Pros:**
- Low impact on git history.
- No dedicated effort required.

**Cons:**
- Inconsistency persists for a long time.
- Doesn't proactively fix type checking ambiguity.

**Effort:** N/A (ongoing)
**Risk:** Very Low

---

### Option 2: Automated Global Update
**Approach:** Use a tool like `pyupgrade` or a custom script to automatically convert legacy `typing` imports to modern syntax across the entire project.

**Pros:**
- Rapidly achieves consistency.
- Removes unnecessary imports.

**Cons:**
- Large diff across many files.
- Potential for small regressions if not verified by a type checker (e.g., `pyright` or `mypy`).

**Effort:** 2-3 hours
**Risk:** Low

## Recommended Action

**To be filled during triage.**

## Technical Details

**Affected files:**
- Most files in `tradingview_scraper/`
- All files in `scripts/`

**Key changes:**
- `List[T]` -> `list[T]`
- `Dict[K, V]` -> `dict[K, V]`
- `Optional[T]` -> `T | None`
- `Union[T1, T2]` -> `T1 | T2`

## Acceptance Criteria

- [ ] All `typing` imports for `List`, `Dict`, `Optional`, `Union` removed where Python 3.10+ equivalents are available.
- [ ] Codebase passes linting and type checking (Pyright/Mypy).
- [ ] No runtime regressions.

## Work Log

### 2026-02-02 - Initial Discovery

**By:** Antigravity

**Actions:**
- Identified legacy typing usage in multiple core files.
- Observed LSP errors related to type ambiguity.
- Created todo entry 009.

## Notes

- This is a low-risk, high-impact cleanup that improves developer experience.
- Ensure the minimum Python version in `pyproject.toml` or `requirements.txt` is actually 3.10+ before proceeding.
