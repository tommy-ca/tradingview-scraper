---
status: pending
priority: p3
issue_id: "025"
tags: ['validation', 'math', 'entropy']
dependencies: []
created_at: 2026-02-02
---

## Problem Statement
Order Validation. Add checks for order > 5 in `permutation_entropy`. The permutation entropy algorithm requires a factorial of the order ($m!$) number of data points for reliable estimation. Orders greater than 5 are rarely justified and lead to computational instability.

## Findings
- **Context**: `permutation_entropy` is used for regime detection and complexity analysis.
- **Issue**: High-order permutations lead to sparse histograms and biased entropy estimates if the input sequence is not exponentially long.
- **Impact**: Incorrect regime detection and unnecessary computational cost if high orders are accidentally specified.

## Proposed Solutions

### Solution A: Strict Validation (Recommended)
Add an explicit check at the beginning of `permutation_entropy` and raise a `ValueError` if `order > 5`.

```python
def permutation_entropy(x, order=3, delay=1):
    if order > 5:
        raise ValueError("Order > 5 is computationally unstable and mathematically discouraged for permutation entropy.")
    # ... implementation
```

### Solution B: Warning and Capping
Issue a `UserWarning` if `order > 5` and optionally cap it or require an explicit `allow_high_order=True` flag.

## Recommended Action
Implement strict validation for the `order` parameter in the `permutation_entropy` function.

## Acceptance Criteria
- [ ] Validation check added to `permutation_entropy`.
- [ ] `ValueError` raised with a clear message when `order > 5`.
- [ ] Unit tests verify that invalid orders are rejected.
- [ ] Docstring updated to mention the constraint and the reasoning.

## Work Log
- 2026-02-02: Issue identified during P3 mathematical audit. Created todo file.
