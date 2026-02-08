# Plan: Clean Worktree with Atomic Commits

## Overview
The current worktree contains a significant amount of uncommitted changes spanning configurations, documentation, scripts, and core library code. This plan aims to clean the worktree by grouping these changes into logical, atomic commits.

## Commit Groupings

### 1. Configuration Changes
**Scope:** `configs/`
**Files:**
- `configs/manifest.json`
- `configs/base/**/*.yaml`
- `configs/scanners/**/*.yaml`

**Proposed Commit Message:**
```
chore(config): update universe definitions and scanner thresholds

- Update manifest.json for new production parameters
- Refine binance spot and perp universe configs
- Adjust scanner thresholds for trend and rating strategies
```

### 2. Documentation Updates
**Scope:** `docs/`
**Files:**
- `docs/audit/*.md`
- `docs/design/*.md`
- `docs/specs/*.md`

**Proposed Commit Message:**
```
docs: update design specs and audit records

- Update feature store resilience and data contracts
- Add rating tuning design document
- Refresh requirements and production workflow specs
- Update plan.md with latest roadmap
```

### 3. Core Orchestration & Pipeline Infrastructure
**Scope:** `tradingview_scraper/orchestration/`, `tradingview_scraper/pipelines/`, `scripts/backtest_engine.py`
**Files:**
- `scripts/backtest_engine.py`
- `tradingview_scraper/orchestration/*.py`
- `tradingview_scraper/pipelines/contracts.py`
- `tradingview_scraper/pipelines/discovery/*.py`
- `tradingview_scraper/portfolio_engines/nautilus_adapter.py`

**Proposed Commit Message:**
```
feat(core): enhance orchestration and backtest engine

- Refactor backtest_engine.py for better performance
- Update stage registry and compute orchestration
- Enhance nautilus adapter for portfolio simulation
- Refine pipeline contracts and discovery logic
```

### 4. Selection & Feature Engineering
**Scope:** `tradingview_scraper/pipelines/selection/`, `tradingview_scraper/utils/`
**Files:**
- `tradingview_scraper/pipelines/selection/stages/*.py`
- `tradingview_scraper/utils/features.py`
- `tradingview_scraper/utils/technicals.py`
- `tradingview_scraper/futures_universe_selector.py`

**Proposed Commit Message:**
```
feat(selection): improve feature engineering and selection policy

- Optimize feature engineering stage
- Refactor inference and policy stages
- Update technical indicator calculations
- Improve futures universe selection logic
```

### 5. Services & Scripts
**Scope:** `scripts/services/`, `scripts/*.py` (remaining)
**Files:**
- `scripts/services/*.py`
- `scripts/run_production_pipeline.py`
- `scripts/run_meta_pipeline.py`
- `scripts/generate_*.py`

**Proposed Commit Message:**
```
feat(services): enhance data ingestion and pipeline scripts

- Improve ingest_data and ingest_features services
- Update backfill_features with strict scope support
- Enhance meta pipeline and reporting scripts
- Refactor consolidate_candidates service
```

### 6. Tests & Cleanups
**Scope:** `tests/`
**Files:**
- `tests/**/*.py`
- Deleted tests

**Proposed Commit Message:**
```
test: update test suite for new features

- Update ingest and compute tests
- Remove obsolete feature consistency tests
- Update pandera contracts tests
```

### 7. Untracked Files (New Features)
**Scope:** New files
**Files:**
- `tradingview_scraper/pipelines/selection/filters/*.py`
- `tradingview_scraper/symbols/stream/fetching.py`
- `docs/plans/`
- New scripts and configs

**Proposed Commit Message:**
```
feat(new): add new filters and helper scripts

- Add advanced trend filters
- Add new audit scripts and debug tools
- Add new plans and design docs
```

## Execution Steps

1.  **Stage and Commit Configs**: `git add configs/` -> `git commit`
2.  **Stage and Commit Docs**: `git add docs/` -> `git commit`
3.  **Stage and Commit Core**: `git add tradingview_scraper/orchestration/ tradingview_scraper/pipelines/discovery/ tradingview_scraper/pipelines/contracts.py tradingview_scraper/portfolio_engines/ scripts/backtest_engine.py` -> `git commit`
4.  **Stage and Commit Selection**: `git add tradingview_scraper/pipelines/selection/ tradingview_scraper/utils/ tradingview_scraper/futures_universe_selector.py` -> `git commit`
5.  **Stage and Commit Services**: `git add scripts/` (careful selection) -> `git commit`
6.  **Stage and Commit Tests**: `git add tests/` -> `git commit`
7.  **Stage and Commit Remaining**: `git add .` -> `git commit`

## Verification
- Run `git status` after each commit to ensure clean progression.
- Run `git log --oneline` at the end to verify history.
