---
status: complete
priority: p2
issue_id: "087"
tags: [architecture, srp]
dependencies: []
created_at: 2026-02-06
---

## Problem Statement
SRP violation in `BacktestEngine`. Risk management logic (`_apply_diversity_constraints`) is hardcoded in the orchestrator.

## Findings
`tradingview_scraper/backtest/engine.py` contains hardcoded 25% caps.

## Proposed Solutions
Move this logic to a dedicated risk module or make it configurable.

## Acceptance Criteria
- [x] `_apply_diversity_constraints` moved to `tradingview_scraper/risk/constraints.py`.
- [x] Diversity cap is now configurable via `TradingViewScraperSettings.cluster_cap`.
