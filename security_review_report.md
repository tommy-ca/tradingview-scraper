# Security Review Report

## Executive Summary
A comprehensive security review was conducted focusing on Run ID sanitization, secure data loading (pickle removal), and path traversal prevention. 
- **Status**: Mixed. Significant progress on sanitization and pickle removal. Critical path traversal vulnerability remains in Ingestion stage.
- **Critical Findings**: 1 (P1)
- **Resolved Findings**: 3

## Detailed Findings

### 1. Ingestion Stage Path Traversal (P1 - Critical)
**Location**: `tradingview_scraper/pipelines/selection/stages/ingestion.py`
**Task**: 052 (Pending)
**Description**: The `IngestionStage` constructs filesystem paths using `SelectionContext.run_id` and explicit path arguments (`candidates_path`, `returns_path`) without ensuring they are anchored to trusted directories.
- `_resolve_candidates_path` returns `self.candidates_path` directly without validation.
- `context.run_id` is used to construct paths via `settings.summaries_runs_dir / context.run_id / "data"`. While `settings.run_id` is validated, `SelectionContext.run_id` lacks inherent validation, creating a potential bypass if the context is manipulated or initialized with untrusted input.
- The recommended fix using `DataLoader.ensure_safe_path()` is **NOT implemented**.

**Remediation**:
- Import `DataLoader` or `SecurityUtils`.
- Wrap all path resolutions in `SecurityUtils.ensure_safe_path()` or `DataLoader(settings).ensure_safe_path()`.

### 2. Run ID Sanitization (Resolved)
**Location**: `tradingview_scraper/settings.py`
**Task**: 028 (Complete)
**Description**: `TradingViewScraperSettings` now includes a `validate_run_id` validator that enforces a strict whitelist (`^[a-zA-Z0-9_\-]+$`). This effectively prevents path traversal characters in the `run_id` when it passes through the settings object.

### 3. Secure Data Loading / Pickle Removal (Resolved)
**Location**: `tradingview_scraper/backtest/engine.py` & `tradingview_scraper/data/loader.py`
**Task**: 029 (Complete)
**Description**: `BacktestEngine.load_data` now delegates to `DataLoader.load_run_data`, which exclusively uses `pd.read_parquet` and `json.load`. No unsafe pickle loading was found in these critical paths.

### 4. Residual Pickle Usage (Resolved)
**Location**: `tradingview_scraper/pipelines/selection/stages/ingestion.py` & `tradingview_scraper/utils/meta_returns.py`
**Task**: 051 (Complete in Code, Pending in TODO)
**Description**: The code in `ingestion.py` and `meta_returns.py` has been updated to remove `pd.read_pickle`.
- `ingestion.py` handles `.parquet` and falls back to `.csv` for other extensions.
- `meta_returns.py` strictly looks for `.parquet` files.
- **Note**: The TODO file `todos/051-complete-p1-incomplete-pickle-removal.md` is still marked as `pending` despite the code being fixed.

## Risk Matrix

| Finding | Severity | Status |
| :--- | :--- | :--- |
| Ingestion Path Traversal | **P1 (Critical)** | 🔴 Vulnerable |
| Run ID Sanitization | P2 (High) | 🟢 Fixed |
| Pickle Loading (Engine) | P1 (Critical) | 🟢 Fixed |
| Pickle Loading (Ingest) | P1 (Critical) | 🟢 Fixed |

## Recommendations
1. **Immediate Action**: Implement Task 052 in `tradingview_scraper/pipelines/selection/stages/ingestion.py` to anchor all resolved paths.
2. **Cleanup**: Update `todos/051-complete-p1-incomplete-pickle-removal.md` to `complete`.
