---
status: complete
priority: p2
issue_id: "067"
tags: [quality, type-checking, lsp, synthesis]
dependencies: []
created_at: 2026-02-05
---

## Problem Statement
Static analysis (LSP) has identified errors in `tradingview_scraper/utils/synthesis.py` related to `ndarray` attribute access and operator overloading.

## Findings
- **Location**: `tradingview_scraper/utils/synthesis.py`
- **Errors**:
    - `Cannot access attribute "shift" for class "ndarray[_AnyShape, dtype[Any]]"`
    - `Operator ">" not supported for types "ArrayLike | Any | Unknown" and "Literal[0]"`

## Proposed Solutions

### Solution A: Type Hinting and Conversions (Recommended)
- `shift` is a Pandas method, not Numpy. Ensure the object is a Series/DataFrame before calling `shift`, or use `np.roll` (with care for fill values) if it's an array. Given this is likely Pandas-heavy logic, casting to Series/DataFrame is probably correct.
- Verify the types involved in the comparison operator.

## Recommended Action
Implement Solution A.

## Acceptance Criteria
- [x] LSP errors resolved in `utils/synthesis.py`.

## Work Log
- 2026-02-05: Identified during code review.
- 2026-02-05: Replaced `shift` call on potentially ambiguous object with `np.roll` on extracted values to ensure type safety and resolve LSP errors. Explicitly handled fill values.
