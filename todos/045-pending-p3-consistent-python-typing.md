---
status: pending
priority: p3
issue_id: "045"
tags: [refactor, typing, technical-debt]
dependencies: []
---

# Consistent Python 3.10+ typing

Final cleanup of remaining legacy typing constructs (`typing.Dict`, `typing.List`, `typing.Union`, `typing.Optional`) in favor of native Python 3.10+ syntax.

## Problem Statement

The codebase has transitioned to Python 3.10+ but still contains legacy typing imports and constructs from `typing`. Python 3.10+ supports native pipe syntax for unions (`int | str`) and lowercase generics for collections (`list[int]`, `dict[str, Any]`). Mixed usage creates visual noise and inconsistency across the project.

Additionally, recent LSP diagnostics show multiple typing errors in `tradingview_scraper/utils/technicals.py` and `backtest_engine.py` related to ambiguous return types and operator support on `ExtensionArray` vs `Series`.

## Findings

- `typing.Dict` and `typing.List` are still used in several core files, including `backtest_engine.py` (though many have already been updated).
- `Union` and `Optional` are still prevalent.
- LSP identifies several "Type is not assignable" errors in `technicals.py`, likely due to lack of `| None` or proper `cast` usage.
- Missing `from __future__ import annotations` in some files where postponement of evaluation would simplify recursive type hints.

## Proposed Solutions

### Option 1: Systematic Cleanup (Recommended)

**Approach:**
1.  Add `from __future__ import annotations` to all core files to enable modern typing syntax even if some dependencies have older runtime requirements (though the platform target is 3.10+).
2.  Use `sed` or `ast-grep` to replace:
    - `typing.List` -> `list`
    - `typing.Dict` -> `dict`
    - `typing.Set` -> `set`
    - `typing.Tuple` -> `tuple`
    - `typing.Union[A, B]` -> `A | B`
    - `typing.Optional[A]` -> `A | None`
3.  Fix the specific "Type is not assignable" errors in `technicals.py` identified by LSP.

**Pros:**
- Clean, modern codebase.
- Reduced import overhead.
- Better compatibility with modern static analysis tools.

**Cons:**
- High churn (many files touched).

**Effort:** 4-6 hours

**Risk:** Low (Type hints only)

## Recommended Action

**To be filled during triage.**

## Technical Details

**Affected files:**
- `scripts/backtest_engine.py`
- `tradingview_scraper/utils/technicals.py`
- `tradingview_scraper/pipelines/selection/stages/feature_engineering.py`
- `tests/test_predictability.py`

**Related components:**
- Pyright / MyPy (Static analysis)

## Acceptance Criteria

- [ ] All `typing.List`, `typing.Dict`, `typing.Union`, `typing.Optional` are replaced with native syntax in the `tradingview_scraper/` package.
- [ ] `from __future__ import annotations` is present in all modified files.
- [ ] LSP/Pyright reporting 0 "Type is not assignable" errors in `technicals.py`.
- [ ] No runtime regressions (verified via existing test suite).

## Work Log

### 2026-02-02 - Initial Discovery

**By:** Antigravity

**Actions:**
- Monitored LSP diagnostics during todo creation.
- Identified specific typing regressions in `technicals.py` and `backtest_engine.py`.
- Drafted cleanup plan in todo 045.

## Notes

- Use `ruff` or `pyupgrade` to automate parts of this transition if possible.
- Pay close attention to `pd.Series` vs `pd.Index` vs `np.ndarray` return types in `technicals.py`.
