---
status: complete
priority: p1
issue_id: "089"
tags: [stability, bug, critical, allocation]
dependencies: []
---

# PyPortfolioOptEngine Signature Mismatch

## Problem Statement
The `PyPortfolioOptEngine` is currently broken due to a signature mismatch in the `_cov_shrunk` call. It passes keyword arguments `kappa_thresh` and `default_shrinkage` which are not accepted by the underlying implementation in `impl/custom.py`. This will cause a `TypeError` and crash the allocation layer at runtime.

## Findings
- **Location**: `tradingview_scraper/portfolio_engines/impl/pyportfolioopt.py:44, 53`
- **Broken Call**: `_cov_shrunk(returns, kappa_thresh=..., default_shrinkage=...)`
- **Implementation**: `tradingview_scraper/portfolio_engines/impl/custom.py:100` defines `_cov_shrunk(returns, shrinkage)`.
- **Severity**: Critical. Blocks any backtest run using the `pyportfolioopt` engine.

## Resolution Summary
- Updated `_cov_shrunk` in `tradingview_scraper/portfolio_engines/impl/custom.py` to accept `kappa_thresh` and `**kwargs`.
- Added alias handling for `default_shrinkage` in `_cov_shrunk`.
- Updated `PyPortfolioOptEngine` in `tradingview_scraper/portfolio_engines/impl/pyportfolioopt.py` to use `shrinkage` parameter name consistently.
- Verified fix with a reproduction script.

## Acceptance Criteria
- [x] `PyPortfolioOptEngine` successfully executes without `TypeError`.
- [x] Test coverage for `PyPortfolioOptEngine` validation.
- [x] Verified against a sample returns matrix.

## Work Log
- 2026-02-07: Identified during security/integrity review.
- 2026-02-08: Fixed signature mismatch in `custom.py` and updated `pyportfolioopt.py` calls. Verified with reproduction script.
