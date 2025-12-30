# Remediation Plan & Issues Log

This file captures the current review findings (bugs + design regressions) and an implementation plan to remediate them.

## Scope
These issues cover pipeline/backtesting/selection changes, scanner/universe-selector architecture risks, and metadata-catalog correctness gaps that impact production runs and backtest validity.

## Implementation Status (2025-12-27)
- [x] BUG-01: Audit persistence fixed.
- [x] BUG-02: Backtest detector initialization fixed.
- [x] BUG-03: Liquidity scoring guards added.
- [x] BUG-04: Backtest report hardened for partial runs.
- [x] LOG-01: Fragility penalty fallback corrected.
- [x] API-01: Currently satisfied (no change required in `tradingview_scraper/symbols/screener.py`).
- [x] RISK-01: Beta audit uses net exposure and aligns dates.
- [x] MAINT-01: Makefile duplication/stale `.PHONY` cleaned up.
- [x] DOC-01: Workflow automation snippet updated.
- [x] MAINT-02: `summaries/` output directory ensured.
- [x] MAINT-03: Summary artifacts moved to `artifacts/summaries/` (`runs/<RUN_ID>/` + `latest` symlink) and all writers updated.

## Metadata Catalog Status (2025-12-28)
- [x] DOC-META-01: Requirements/specs/design docs updated for profile + PIT.
- [x] META-01: Persist `profile` in `data/lakehouse/symbols.parquet` (PIT versioned).
- [x] META-02: Align timezone/session resolution with TradingView API and exchange defaults (remove hardcoded UTC/24x7 for non-crypto).
- [x] META-03: Bootstrap and maintain `data/lakehouse/exchanges.parquet`.
- [x] META-04: Add meaningful-change detection to avoid SCD churn.

## Universe Selector Status (2025-12-28)
- [x] DOC-UNI-01: Document selector architecture and refactor roadmap.
- [x] UNI-01: Add config lint for all `configs/**/*.yaml` (see `scripts/lint_universe_configs.py` + `make scan-lint`).
- [x] UNI-02: Add run scoping for scan outputs (`export/<run_id>/...`) and a stable export envelope (`{meta,data}`) while keeping legacy exports compatible.
- [x] UNI-03: Update downstream consumers to prefer export `meta` over filename parsing.
- [ ] UNI-04: Introduce a manifest-driven scan runner (replaces duplicated bash config lists).
- [ ] UNI-05: Refactor `FuturesUniverseSelector` monolith into modules. (Done: `build_payloads()` now matches `run()` execution and `--dry-run` output.)

### Fix References
- BUG-01: `scripts/optimize_clustered_v2.py` now writes `AUDIT_FILE` after setting `full_audit["optimization"]`.
- BUG-02: `scripts/backtest_engine.py` initializes `MarketRegimeDetector` unconditionally.
- BUG-03: `scripts/natural_selection.py` clamps/guards the liquidity spread proxy when ATR/price are missing.
- BUG-04: `scripts/generate_backtest_report.py` tolerates missing profile JSONs/rows and outputs `N/A` instead of crashing.
- LOG-01: `scripts/optimize_clustered_v2.py` derives a penalty-compatible `fragility` when `Fragility_Score` is absent.
- RISK-01: `scripts/optimize_clustered_v2.py` computes beta using `Net_Weight` when present and normalizes date indices.
- MAINT-01: `Makefile` deduplicates `recover` and trims stale `.PHONY` targets.
- DOC-01: `docs/specs/quantitative_workflow.md` automation snippet updated to use the new `make` workflow.
- MAINT-03: Summary writers use `tradingview_scraper/settings.py` and write under `artifacts/summaries/runs/<RUN_ID>/` with `artifacts/summaries/latest` as a symlink.
- UNI-02: `tradingview_scraper/symbols/utils.py` supports run-scoped exports via `TV_EXPORT_RUN_ID`; selector exports use `{meta,data}`.
- UNI-03: `scripts/*` consumers resolve `export/<run_id>/` and prefer embedded `meta` (direction/product/exchange) over filename parsing.
- UNI-05: `tradingview_scraper/futures_universe_selector.py` uses `build_payloads()` for both execution and `--dry-run`.

### Validation Notes
- `uv run -m compileall -q scripts tradingview_scraper` completed.
- Smoke: created a conflicting export (`filename != meta`) under `export/smoke-uni-02-03/` and ran `RUN_ID=smoke-uni-02-03 make prep-raw`; `data/lakehouse/selection_audit.json` reported `OKX_PERP` + `short=1`, confirming consumers prefer `meta` over filename parsing.
- `uv run pytest -q tests/test_regime.py tests/test_loader_lookback.py tests/test_indicators.py` passed.
- Full `pytest` run is network-heavy and may timeout depending on environment.

## Issues

| ID | Severity | Area | File / Location | Problem | Impact | Recommended Fix |
| --- | --- | --- | --- | --- | --- | --- |
| BUG-01 | High | Audit persistence | `scripts/optimize_clustered_v2.py` | Optimization metadata was computed but not written back to `data/lakehouse/selection_audit.json`. | Downstream analysis misses optimization metadata; misleading logs. | Write `full_audit` back to `AUDIT_FILE` after updating. |
| BUG-02 | High | Backtest reliability | `scripts/backtest_engine.py` | Regime detector initialization could be missing depending on stats availability. | Backtest crash in fresh/partial runs. | Initialize detector unconditionally. |
| BUG-03 | High | Selection correctness | `scripts/natural_selection.py` | Liquidity score could reward missing ATR/price by exploding spread proxy. | Selects low-quality or incomplete-data symbols as “most liquid”. | Guard invalid inputs and clamp inverse spread ratio. |
| BUG-04 | High | Reporting robustness | `scripts/generate_backtest_report.py` | Assumed all profiles existed and indexed empty selections. | Report generation crashes on partial profile runs. | Make report tolerant of missing files/rows and render N/A. |
| LOG-01 | Medium | Risk penalty semantics | `scripts/optimize_clustered_v2.py` | Fragility fallback could incorrectly penalize antifragility (reward metric). | Backtests/production can invert intended penalty behavior. | Derive a compatible fragility penalty when `Fragility_Score` missing. |
| API-01 | Medium | Public API contract | `tradingview_scraper/symbols/screener.py` | Risk of raising on retry exhaustion if exceptions escape. | Downstream callers break unexpectedly. | Ensure the public method returns `{status: failed}` for recoverable failures. |
| RISK-01 | Medium | Beta audit correctness | `scripts/optimize_clustered_v2.py` | Beta calculation used gross `Weight` and could misalign dates. | Misstates systemic exposure for hedged/short profiles. | Use `Net_Weight` and normalize indices for alignment. |
| MAINT-01 | Low | Makefile correctness | `Makefile` | `recover` ran twice and `.PHONY` listed stale targets. | Wasted runtime / operational confusion. | Deduplicate and prune stale `.PHONY`. |
| DOC-01 | Low | Documentation drift | `docs/specs/quantitative_workflow.md` | Automation snippet referenced legacy scripts. | Operators follow incorrect steps. | Update to new `make` targets. |
| MAINT-02 | Low | Output directory assumptions | backtest/report scripts | Wrote to `summaries/` without ensuring directory exists. | First-time runs fail depending on command order. | `os.makedirs("summaries", exist_ok=True)` before writing. |
| MAINT-03 | Medium | Artifact hygiene | pipeline/report scripts + Makefile + docs | Summary artifacts were written to `summaries/` without run scoping/history. | Hard to audit, cluttered workspace, brittle publishing assumptions. | Write to `artifacts/summaries/runs/<RUN_ID>/` and maintain `artifacts/summaries/latest` as a symlink; sync only `latest/` to gist. |
| META-01 | High | Metadata survivorship | `tradingview_scraper/symbols/stream/metadata.py` | `profile` is required for market-aware logic but not persisted/versioned in the catalog. | Profile heuristics can drift over time, introducing survivorship/look-ahead bias in backtests. | Persist `profile` in `symbols.parquet` and include it in PIT versioning and audits. |
| META-02 | High | Timezone/session correctness | `tradingview_scraper/symbols/stream/persistent_loader.py`, `scripts/build_metadata_catalog.py` | Runtime enrichment and catalog builds can coerce `timezone`/`session` to `UTC/24x7` even when TradingView provides localized values or when non-crypto defaults should apply. | Breaks market-hours logic and invalidates session-aware backtests/health checks. | Centralize resolution (API -> exchange defaults -> fallback) and remove non-crypto `24x7` coercion. |
| META-03 | Medium | Exchange catalog availability | `data/lakehouse/exchanges.parquet` | Exchange catalog may be missing or stale, but multiple audits/docs assume it exists. | Default resolution becomes inconsistent; audits fail; operator confusion. | Bootstrap and maintain `exchanges.parquet` from `DEFAULT_EXCHANGE_METADATA` and observed exchanges. |
| META-04 | Medium | SCD churn | `tradingview_scraper/symbols/stream/metadata.py` | Upserts may version symbols even when no meaningful fields changed. | Unnecessary PIT bloat; noisy diffs; slower audits. | Add meaningful-change detection before creating a new version. |
| DOC-META-01 | Low | Documentation alignment | `docs/metadata_schema_guide.md`, `docs/specs/metadata_timezone_spec.md` | Requirements/spec/design docs must reflect API-synced schema and PIT-safe usage. | Operators follow incorrect workflows; inconsistencies persist. | Update docs to require persisted `profile`, API-synced resolution, and incremental updates. |
| DOC-UNI-01 | Low | Documentation alignment | `docs/specs/quantitative_workflow.md` | Universe selector architecture and refactor plan not captured in specs. | Operators and developers lack a shared contract; changes become risky. | Document current selector contract + staged roadmap. |
| UNI-01 | High | Config safety | `configs/**/*.yaml`, selector config loader | Contradictory flags and unsupported screener fields are not detected before runtime. | Empty universes or HTTP 400 failures during scans. | Add a fast config lint step (CI-safe) and enforce basic invariants. |
| UNI-02 | High | Export contract | `export/<run_id>/universe_selector_*.json` consumers | Downstream scripts infer semantics from filenames (underscore splits / `_short`). | Hidden coupling; fragile renames; cross-run leakage. | Introduce `{meta,data}` envelope + `export/<run_id>/...` while keeping legacy compatibility. |
| UNI-03 | Medium | Consumer robustness | `scripts/select_top_universe.py`, `scripts/prepare_portfolio_data.py` | Consumers prefer filename parsing and globbing over structured metadata. | Incorrect direction/category parsing; stale file mixing. | Prefer `meta` when present; keep legacy filename parsing as fallback. |
| UNI-04 | Medium | Orchestration DRY | `scripts/run_*_scans.sh`, Makefile scan targets | Scan config lists are duplicated across bash scripts and ad hoc runners. | Drift and partial coverage; hard to add/remove scans safely. | Add a manifest-driven scan runner and have Makefile call it. |
| UNI-05 | Medium | Selector correctness | `tradingview_scraper/futures_universe_selector.py`, `tradingview_scraper/pipeline.py` | `dry_run` payload generation can diverge from real `run()` behavior (especially with exchange loops). | Async pipeline scans the wrong payload set; hard-to-debug misses. | Add `build_payloads()` that matches execution and refactor selector into modules. |

## Remediation Plan

### Phase 1 — Persistence & Reliability (BUG-01, BUG-02, BUG-04, MAINT-02, MAINT-03)
1. Restore audit persistence in `scripts/optimize_clustered_v2.py`.
2. Initialize `MarketRegimeDetector` unconditionally in `scripts/backtest_engine.py`.
3. Ensure summary artifacts are written under `artifacts/summaries/runs/<RUN_ID>/` and `artifacts/summaries/latest` points at the current run.
4. Make `scripts/generate_backtest_report.py` robust to missing profile files/rows.

### Phase 2 — Quantitative Semantics & Selection Safety (BUG-03, LOG-01)
1. Fix liquidity scoring to avoid rewarding missing ATR/price.
2. Ensure “fragility” remains a penalty even when stats are simplified.

### Phase 3 — API Contract & Risk Audit (API-01, RISK-01)
1. Ensure screener methods return failure dicts for recoverable failures.
2. Compute beta using `Net_Weight` and align indices.

### Phase 4 — Maintenance & Documentation (MAINT-01, DOC-01)
1. Fix Makefile duplication and stale `.PHONY` entries.
2. Update workflow docs to match the new pipeline targets.

### Phase 5 — Metadata Catalog Correctness (META-01, META-02, META-03, META-04, DOC-META-01)
1. Align all metadata writers to a shared resolver (API -> exchange defaults -> fallback).
2. Persist `profile` in `symbols.parquet` and include it in PIT versioning.
3. Bootstrap and maintain `exchanges.parquet` for exchange defaults.
4. Add meaningful-change detection to reduce SCD churn.
5. Regenerate metadata audits/reports and confirm invariants.

### Phase 6 — Universe Selector Hardening & Refactor (UNI-01, UNI-02, UNI-03, UNI-04, UNI-05, DOC-UNI-01)
1. Add a config lint step for all `configs/**/*.yaml` (implemented via `scripts/lint_universe_configs.py` + `make scan-lint`; enforce in CI workflows).
2. Introduce a stable scan export envelope (`{meta,data}`) and run scoping (`export/<run_id>/...`) while keeping legacy exports compatible.
3. Update downstream consumers to prefer `meta` over filename parsing.
4. Replace duplicated bash scan lists with a manifest-driven scan runner.
5. Refactor selector internals (split monolith + introduce `build_payloads()` that matches real execution).

### Phase 7 — Multi-Engine Portfolio Optimization (Finalized)
1. Implement `BaseRiskEngine` interface for library-agnostic optimization.
2. Maintain **Custom (Internal)** engine as the primary baseline for the 4 standard profiles (MinVar, HRP, MaxSharpe, Barbell).
3. Integrate `skfolio`, `Riskfolio-Lib`, `PyPortfolioOpt`, and `CVXPortfolio` as comparative backends.
4. Extend `BacktestEngine` with Tournament Mode to benchmark all engines (Custom + 4 Libraries) under the same constraints.
5. **Reproducible Workflow Manifests**: Implement `configs/manifest.json` with multi-profile support and schema validation.

### Phase 8 — Centralized Discovery Configuration (Finalized)
1. **Discovery Schema**: Extend `manifest.schema.json` to include universe selector parameters (thresholds, enabled markets).
2. **Selector Integration**: Update `BaseUniverseSelector` to ingest config from manifest profiles instead of external YAMLs.
3. **Workflow Refactoring**: Update `make scan-all` and shell scripts to propagate `PROFILE` to discovery engines.
4. **Validation**: Extend `make scan-lint` to validate the JSON discovery block against market-specific invariants.

### Phase 9 — Multi-Simulator Backtesting Framework
1. **Simulator Abstraction**: Refactor `BacktestEngine` to support modular simulation backends (`BaseSimulator`).
2. **Returns Simulator**: Move existing idealized dot-product logic to a formal `ReturnsSimulator`.
3. **CVXPortfolio Simulator**: Implement high-fidelity `CvxPortfolioSimulator` with transaction cost modeling (5bps slippage, 1bp commission).
4. **Lakehouse Bridge**: Implement `LakehouseDataInterface` to provide Prices/Returns/Volumes from Parquet to `cvxportfolio`.
5. **Alpha Decay Audit**: Update tournament reporting to compare Idealized vs. Realized Sharpe ratios.

## Acceptance Criteria
- `data/lakehouse/selection_audit.json` contains an `optimization` section after `scripts/optimize_clustered_v2.py` runs.
- Summary writers create `artifacts/summaries/runs/<RUN_ID>/` and update `artifacts/summaries/latest` as needed.
- Liquidity scoring does not rank assets higher when ATR/price are missing.
- Beta audit reflects hedged exposure (SHORTs reduce beta rather than inflating it).
- `data/lakehouse/exchanges.parquet` exists and covers all exchanges present in `data/lakehouse/symbols.parquet`.
- Non-crypto symbols are not coerced to `timezone=UTC` / `session=24x7`; crypto remains `UTC/24x7`.
- `profile` is persisted and versioned in `data/lakehouse/symbols.parquet` and used for PIT-safe backtests.
- All `configs/**/*.yaml` pass config lint (no contradictions; field portability guards catch known HTTP 400 issues).
- Scan outputs can be scoped by run (`export/<run_id>/...`) and consumers prefer structured `meta` over filename parsing.
- `build_payloads()` (or equivalent) matches real selector execution so async discovery cannot under/over-scan.
