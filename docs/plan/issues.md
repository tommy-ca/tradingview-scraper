# Remediation Plan & Issues Log

This file captures the current review findings (bugs + design regressions) and an implementation plan to remediate them.

## Scope
These issues are limited to the pipeline/backtesting/selection changes in the current working tree.

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

### Fix References
- BUG-01: `scripts/optimize_clustered_v2.py` now writes `AUDIT_FILE` after setting `full_audit["optimization"]`.
- BUG-02: `scripts/backtest_engine.py` initializes `MarketRegimeDetector` unconditionally.
- BUG-03: `scripts/natural_selection.py` clamps/guards the liquidity spread proxy when ATR/price are missing.
- BUG-04: `scripts/generate_backtest_report.py` tolerates missing profile JSONs/rows and outputs `N/A` instead of crashing.
- LOG-01: `scripts/optimize_clustered_v2.py` derives a penalty-compatible `fragility` when `Fragility_Score` is absent.
- RISK-01: `scripts/optimize_clustered_v2.py` computes beta using `Net_Weight` when present and normalizes date indices.
- MAINT-01: `Makefile` deduplicates `recover` and trims stale `.PHONY` targets.
- DOC-01: `docs/specs/quantitative_workflow.md` automation snippet updated to use the new `make` workflow.
- MAINT-02: `scripts/backtest_engine.py` and `scripts/generate_backtest_report.py` ensure `summaries/` exists.

### Validation Notes
- `python -m compileall -q scripts tradingview_scraper` completed.
- `pytest -q tests/test_regime.py tests/test_loader_lookback.py tests/test_indicators.py` passed.
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

## Remediation Plan

### Phase 1 — Persistence & Reliability (BUG-01, BUG-02, BUG-04, MAINT-02)
1. Restore audit persistence in `scripts/optimize_clustered_v2.py`.
2. Initialize `MarketRegimeDetector` unconditionally in `scripts/backtest_engine.py`.
3. Ensure `summaries/` exists before writing backtest outputs.
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

## Acceptance Criteria
- `data/lakehouse/selection_audit.json` contains an `optimization` section after `scripts/optimize_clustered_v2.py` runs.
- Backtest/report scripts create `summaries/` as needed.
- Liquidity scoring does not rank assets higher when ATR/price are missing.
- Beta audit reflects hedged exposure (SHORTs reduce beta rather than inflating it).
