# 🛠️ Quantitative Platform: Issues & Fixes

## ✅ Recently Fixed
- [x] **Selection Metadata Enrichment**: `scripts/enrich_candidates_metadata.py` now automatically detects and enriches the full returns universe with institutional defaults (`tick_size`, `lot_size`, etc.).
- [x] **Audit Ledger Hashing**: `tradingview_scraper/utils/audit.py` now handles mixed-type DataFrames (strings/floats) correctly.
- [x] **CVXPortfolio Simulator Fidelity**: Strictly aligned weight indices with rolling returns and standardized on `cash` modeling to prevent solver crashes.
- [x] **Dynamic Strategy Resume**: `scripts/generate_reports.py` now automatically identifies and highlights the best engine per profile in the strategy resume.
- [x] **Regime-Specific Attribution**: Fixed data loading priority in `generate_reports.py` to ensure window-level regime metrics are captured from `tournament_results.json`.
- [x] **Atomic & Safe Audit Writes**: Implemented Unix file locking (`fcntl`) in `scripts/natural_selection.py` to prevent corruption of the shared `selection_audit.json`.
- [x] **Settings Precedence Clarified**: CLI init overrides now take priority, followed by `.env`, OS env, manifest profile, manifest defaults, then code defaults.
  - **Implemented**: `tradingview_scraper/settings.py` settings source order.
  - **Documented**: `docs/specs/workflow_manifests.md`.
  - **Tests**: `tests/test_settings_precedence.py` (lookback, backtest windows, cluster cap, backtest simulators, TV_PROFILE precedence).
  - **Validated**: `uv run pytest tests/test_settings_precedence.py` (14 passed); `TV_PROFILE=development ... --export-env` shows `LOOKBACK=60`, `PORTFOLIO_LOOKBACK_DAYS=60`.
  - **CI**: `.github/workflows/settings-precedence.yml` runs the precedence test suite on relevant changes.

## ⚠️ High Priority: Needs Follow-up (Audit Findings)
- [ ] **None currently.**

## ✅ High Priority: Completed (Audit Validated)
- [x] **Tournament Window Mismatch**: `tournament_results.json` now matches manifest train/test windows.
  - **Root Cause**: `scripts/backtest_engine.py` defaulted to hardcoded 120/20/20 and ignored manifest settings when args were omitted.
  - **Fix**: Default `run_tournament` windows to `get_settings()` values when args are `None`; CLI defaults to `None` and resolves to settings.
  - **Implemented**: `scripts/backtest_engine.py`.
  - **Validated**: Run `20260103-010147` (dev profile, minimal tournament) reports `train_window=30`, `test_window=10`, `step_size=10`.
- [x] **Lookback Wiring Mismatch** *(Reopened)*: `data_prep` now honors manifest lookback for dev profile.
  - **Root Cause**: `PORTFOLIO_LOOKBACK_DAYS` was exported as a fixed default (365), overriding manifest lookback.
  - **Fix**: `portfolio_lookback_days` now resolves to `lookback_days` when unset; export uses resolved value; data prep and audit checks use resolved value.
  - **Implemented**: `tradingview_scraper/settings.py`, `scripts/prepare_portfolio_data.py`, `scripts/validate_portfolio_artifacts.py`.
  - **Validated**: Run `20260103-010210` logs `data_prep` intent with `lookback_days: 60` in `audit.jsonl`.
- [x] **Run Log Artifacts Missing**: `audit.jsonl` references step log files, but the run log directory is empty.
  - **Validated**: Run `20260103-004810` has populated logs (`01_cleanup.log` ... `14_gist_sync.log`).
- [x] **Missing Optimization Output Artifact**: Optimization succeeds but no `portfolio_optimized_v2.json` is present.
  - **Validated**: `data/lakehouse/portfolio_optimized_v2.json` exists after run `20260103-004810`.

## ✅ High Priority: Completed (Logic Integrity)
- [x] **Standardize `run_selection` API** *(Audit: Confirmed)*: Ensure all internal calls use a consistent 5-tuple return or a typed `SelectionResponse` object.
  - **Symptoms**: Call sites rely on positional tuple unpacking, which is brittle across engine versions.
  - **Evidence**: `SelectionResponse` exists in `tradingview_scraper/selection_engines/base.py`, but `scripts/natural_selection.py` returns a tuple and callers unpack positional values.
  - **Likely files**: `scripts/natural_selection.py`, `scripts/backtest_engine.py`, selection engine modules under `tradingview_scraper/selection_engines/`.
  - **Fix**: Return `SelectionResponse` from `run_selection` and update call sites to use named fields.
  - **Implemented**: `scripts/natural_selection.py`, `scripts/backtest_engine.py`, `scripts/tournament_normalization.py`, `scripts/tournament_v2_vs_v2_1.py`, `scripts/diagnose_v3_internals.py`, `scripts/cache_selection_features.py`, `tests/test_natural_selection_*`.
  - **Validate**: Run `uv run pytest tests/test_selection_*` and confirm no API mismatches.
- [x] **Alpha Isolation Baseline** *(Audit: Confirmed)*: Ensure the `market` engine is automatically included in tournament runs so alpha isolation has a baseline.
  - **Symptoms**: Alpha isolation reports can omit the market baseline when tournament defaults are used.
  - **Evidence**: `scripts/generate_reports.py` reads `all_results[sim].market`, but `scripts/backtest_engine.py` only injects `market` when `settings.dynamic_universe` is true.
  - **Likely files**: `scripts/backtest_engine.py`, `scripts/generate_reports.py`.
  - **Fix**: Inject baseline `market` profiles during tournaments regardless of `dynamic_universe`.
  - **Implemented**: `scripts/backtest_engine.py`.
  - **Validate**: Re-run `make port-test` and confirm `market` appears in `tournament_results.json`.
- [x] **Tournament Outputs Empty** *(Audit: Confirmed)*: `backtest_engine.py` interprets empty CLI args as empty lists, resulting in `tournament_results.json` with no simulators or results. Treat empty lists as defaults or avoid splitting empty args.
  - **Symptoms**: `tournament_results.json` has `simulators: []` and `results: {}`.
  - **Evidence**: Observed in run `20260102-230609` (see Audit Context).
  - **Likely files**: `scripts/backtest_engine.py`.
  - **Fix**: Convert empty list inputs to `None` so defaults apply; avoid `.split(",")` on empty args.
  - **Implemented**: `scripts/backtest_engine.py`.
  - **Validate**: Run `uv run scripts/backtest_engine.py --tournament` and confirm results are populated.
- [x] **Barbell Profile Missing** *(Audit: Confirmed)*: `optimize_clustered_v2.py` logs barbell but only writes it when `antifragility_stats.json` exists. Ensure antifragility stats are generated before optimization or explicitly skip/flag barbell in outputs.
  - **Symptoms**: Optimization logs mention barbell, but `portfolio_optimized_v2.json` lacks `profiles.barbell`.
  - **Evidence**: Observed in run `20260102-230609` (see Audit Context).
  - **Likely files**: `scripts/optimize_clustered_v2.py`, `scripts/port-analyze` pipeline.
  - **Fix**: Add an antifragility stats generation step before optimization or add a clear skip banner in outputs.
  - **Implemented**: `Makefile`, `scripts/optimize_clustered_v2.py`.
  - **Validate**: Re-run optimization and confirm `profiles.barbell` appears or is explicitly marked as skipped.
- [x] **Alignment Policy Breach (TradFi)** *(Audit: Confirmed)*: `prepare_portfolio_data.py` zero-fills missing days (`fillna(0.0)`), which conflicts with “no padding” for TradFi calendars. Implement market-day alignment (session calendar) without weekend padding.
  - **Symptoms**: TradFi returns include padded weekend zeros, distorting correlations.
  - **Evidence**: `scripts/prepare_portfolio_data.py` has `returns_df = returns_df.fillna(0.0)`.
  - **Likely files**: `scripts/prepare_portfolio_data.py`.
  - **Fix**: Align by market sessions (per-asset calendars) and avoid zero-filling for TradFi.
  - **Implemented**: `scripts/prepare_portfolio_data.py`, `scripts/optimize_clustered_v2.py`, `tradingview_scraper/portfolio_engines/cluster_adapter.py`.
  - **Validate**: Re-run health audit and confirm no weekend padding for equities.

## ✅ Medium Priority: Completed (Enhancements)
- [x] **Solver Dampening**: Add numerical regularizers to `cvxportfolio` to prevent "Variable value must be real" failures when encountering extreme survivorship bias winners (e.g., highly volatile crypto).
  - **Likely files**: `tradingview_scraper/portfolio_engines/` and CVX solver wrappers.
  - **Fix**: Add epsilon jitter to covariance, constrain weight bounds, and/or add L2 penalties.
  - **Implemented**: `tradingview_scraper/portfolio_engines/engines.py`.
  - **Validate**: Run the tournament with high-volatility assets and confirm solver stability.
## ✅ Medium Priority: Completed (Enhancements)
- [x] **Automated RUN_ID Detection** *(Audit: Confirmed)*: Report generator currently auto-detects, but could be smarter about identifying the *last finished* run vs just the last created directory.
  - **Evidence**: `_detect_latest_run()` in `scripts/generate_reports.py` selects the lexicographically last run directory without checking artifact completeness.
  - **Likely files**: `scripts/generate_reports.py`, `tradingview_scraper/settings.py`.
  - **Fix**: Prefer runs with complete logs and key artifacts, not merely latest mtime.
  - **Implemented**: `scripts/generate_reports.py`.
  - **Validate**: Compare report selection across multiple runs and verify correct run chosen.
- [x] **Canonical Latest Pointer** *(Audit: Confirmed)*: `artifacts/summaries/latest` is correct but `artifacts/summaries/runs/latest` can become stale and mislead audits. Standardize or remove the redundant path.
  - **Evidence**: Observed in run `20260102-230609` (see Audit Context).
  - **Likely files**: `tradingview_scraper/settings.py`, any doc references.
  - **Fix**: Make `summaries/latest` authoritative and avoid creating `runs/latest` or document it as legacy.
  - **Implemented**: `tradingview_scraper/settings.py`.
  - **Validate**: Ensure audits reference the symlink target for the most recent run.

## ✅ Technical Debt: Completed
- [x] **Typed Settings**: Move more environment-variable based flags into the `pydantic` settings model.
  - **Likely files**: `tradingview_scraper/settings.py`, `Makefile`.
  - **Fix**: Promote ad-hoc env vars to settings fields and export them consistently.
  - **Implemented**: `tradingview_scraper/settings.py`, `scripts/prepare_portfolio_data.py`.
  - **Validate**: `uv run python -m tradingview_scraper.settings --export-env` matches expected env set.
- [x] **Nautilus Full Integration**: Complete the event-driven strategy adapter for `NautilusSimulator`.
  - **Likely files**: `tradingview_scraper/portfolio_engines/backtest_simulators.py` and Nautilus adapter modules.
  - **Fix**: Implement interface parity with existing simulators and add tests.
  - **Implemented**: `tradingview_scraper/portfolio_engines/nautilus_adapter.py`, `tradingview_scraper/portfolio_engines/backtest_simulators.py`.
  - **Validate**: Include `nautilus` in tournament simulators and confirm successful runs (parity fallback if Nautilus is unavailable).

## 🔍 Audit Context (Most Recent)
- **Run ID:** `20260103-010210` (development profile, data prep validation)
- **Additional Validation Runs:** `20260103-010147` (dev tournament windows), `20260103-005936` (prod tournament)
- **Key Artifacts:** `artifacts/summaries/runs/20260103-010210/audit.jsonl`, `artifacts/summaries/runs/20260103-010147/tournament_results.json`, `artifacts/summaries/runs/20260103-005936/tournament_results.json`
- **Ledger Integrity:** Verified via `scripts/verify_ledger.py`
- **Notable Observations:** `data_prep` now logs `lookback_days: 60` (dev); dev tournament meta matches manifest (30/10/10); production tournament meta remains 120/20/20 per defaults.

## ✅ Validation Checklist
- [x] Re-run Step 5 (data-fetch lightweight) and confirm `audit.jsonl` logs correct lookback days.
- [x] Re-run tournament and confirm `tournament_results.json` includes simulators + results, and `returns/` is populated.
- [x] Re-run tournament and confirm `train_window`, `test_window`, `step_size` match `resolved_manifest.json`.
- [x] Re-run optimization and confirm `profiles.barbell` appears in `portfolio_optimized_v2.json` (or is explicitly skipped with a warning).
- [ ] Verify health audits remain clean after alignment changes (no padded weekends).
- [x] Confirm run log files are written to `artifacts/summaries/runs/<RUN_ID>/logs/`.
- [x] Confirm `data/lakehouse/portfolio_optimized_v2.json` exists post-optimization.
