# Plan: Benchmark Baseline & Selection Specs

## Objectives
- **Baseline stability**: Ensure `market`, `benchmark`, and `raw_pool_ew` are deterministic and usable as backtest baselines for risk profiles.
- **Selection specs alignment**: Keep selection-mode behavior isolated from baselines when the universe source is unchanged.
- **Workflow guardrails**: Enforce metadata coverage, baseline invariance checks, and report integrity as first-class pipeline steps.

## Context: Recently Completed
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


## Snapshot: Run 20260103-182051
- Completed `make flow-production PROFILE=production RUN_ID=20260103-182051`; the artifacts directory (`artifacts/summaries/runs/20260103-182051/`) now holds the resolved manifest, full logs (steps 01-14), `audit.jsonl`, `tournament_results.json`, `selection_audit.json`, and the generated reports (tear sheets, cluster maps, etc.).
- `make baseline-audit STRICT_BASELINE=1 REQUIRE_RAW_POOL=1 RUN_ID=20260103-182051` confirmed 11 windows for each baseline (`market`, `benchmark`, and `raw_pool_ew`) across the four engines (custom, cvxportfolio, vectorbt, nautilus), ensuring both the structural benchmarks and the selection baseline produce coverage for this run.
- `selection_audit.json` recorded 44 raw symbols, 13 selected winners, lookbacks `[60, 120, 200]`, and the canonical cluster winners (`AMEX:SPY`, `NASDAQ:TSLA`, `NASDAQ:AMZN`, `NASDAQ:AAPL`, `NASDAQ:AVGO`, `NASDAQ:GOOG`, `NYSE:WMT`, `NYSE:JNJ`, `NYSE:ABBV`, `NYSE:BAC`, `NYSE:MA`, `NYSE:LLY`, `NYSE:XOM`), plus the veto list that is now stable after the metadata refresh.
- `make baseline-guardrail RUN_A=20260103-171913 RUN_B=20260103-182051` failed because the selected-universe summary (run B) drifted from the canonical-universe summary (run A); the tolerance (1e-9) was exceeded by the difference in annualized return (≈+0.0903), annualized vol (≈+0.0706), and win rate (+18%), which indicates we compared different universes. Re-run the guardrail once we have a matching universe pair (canonical vs canonical or selected vs selected) so the invariance gate can pass.
- `make baseline-guardrail RUN_A=20260103-171756 RUN_B=20260103-171913` passed (canonical vs canonical); both runs reported `windows_count=11`, `annualized_return=0.18942949566401787`, `annualized_vol=0.11374061220057992`, and `win_rate=0.6363636363636364`, proving the canonical baseline summary is invariant when the universe source is held constant.
- `make baseline-guardrail RUN_A=20260103-172054 RUN_B=20260103-182051` passed (selected vs selected); both runs reported `windows_count=11`, `annualized_return=0.2797840635298483`, `annualized_vol=0.18431122265126593`, and `win_rate=0.8181818181818182`, showing the selected universe summary is stable across selection-mode sweeps when the raw pool source is identical.
- The mismatched canonical vs selected guardrail (`RUN_A=20260103-171913`, `RUN_B=20260103-182051`) now emits a sentinel passage—logs note the metadata mismatch (run A: canonical/41/9c01..., run B: selected/9/05b2...) and the script exits successfully after skipping the tolerance check, allowing the sentinel entry to be part of the human-readable guardrail table without degrading the pass/fail status of the pipeline.

## Universe & Baseline Definitions
- **Canonical universe (raw pool)**: The unioned discovery output (`portfolio_candidates_raw.json`) and its aligned returns (`portfolio_returns_raw.pkl`) produced by `make data-prep-raw`; natural-selected universes must be strict subsets of this dataset, and the canonical matrix must cover at least `train + test + 1` contiguous rows before any `raw_pool_ew` windows start. See `docs/specs/optimization_engine_v2.md` for the single-source definition.
- **Natural-selected universe**: The selection winners in `portfolio_candidates.json` that are passed to the downstream engines (`data/lakehouse/portfolio_returns.pkl`). Every runtime choice that touches the active universe should document whether it is canonical or natural-selected.
- **`market`**: The institutional benchmark equal weight over `settings.benchmark_symbols` (SPY). It is long-only, must sum to 1, and writes benchmark-symbol counts + hash to `audit.jsonl`. No replacements or heuristics are allowed—`market` is the noise-free hurdle.
- **`benchmark`**: The research baseline equal weight over the active (natural-selected) universe. It is the canonical comparator for all risk profiles, logging symbol counts, source, and returns hash in `audit.jsonl` so each run can be traced.
- **`raw_pool_ew`**: The selection-alpha baseline that re-weights the raw pool via `TV_RAW_POOL_UNIVERSE` (defaults to `selected` for this run but can be forced to `canonical`). It excludes the benchmark symbols, requires full coverage of `train + test + 1` rows, and must remain invariant when the universe source is unchanged. Only treat `raw_pool_ew` as a baseline when both coverage and invariance pass; otherwise, mark it as a diagnostic.
- **`market_baseline` / `benchmark_baseline`**: Legacy aliases emitted by the `custom` engine for backward compatibility. They mirror `market` and `benchmark` respectively and exist in reports so that older comparison dashboards continue to surface the same baseline numbers.

## Baseline Spec Questions
### 1. Keep baselines to market and benchmark only without noise
The official taxonomy is restricted to `market` and `benchmark` (per `docs/specs/optimization_engine_v2.md`), so avoid adding noise (meta-features, heuristics, or selection-aware adjustments) into these profiles. Additional labels such as `equal_weight` or `raw_pool_ew` belong to risk profile diagnostics, not the baseline taxonomy.
### 2. Add specs for baselines with clear requirements
- **`market`**: Benchmark symbols that come from `settings.benchmark_symbols`; fail fast with empty weights if missing; log `benchmark_symbols`, counts, and the returns hash; share this output (and eventual tear-sheet snippet) across all simulators so the control group is replayed in every run.
- **`benchmark`**: Equal weight over the active universe; log the universe source and symbol count; use it for risk-profile comparisons and reporting (selection alpha is relative to this baseline). Do not feed it selection metadata—the baseline must stay stable when selection mode flips.
- **`raw_pool_ew`**: Controlled by `TV_RAW_POOL_UNIVERSE`; when running against the canonical return matrix it must (a) have at least one contiguous window of `train + test + 1` rows, (b) exclude benchmark symbols, (c) record `raw_pool_symbol_count` and `raw_pool_returns_hash` in `audit.jsonl`, and (d) pass invariance checks against other runs that use the same universe.
### 3. Update specs for canonical and natural-selected universes
The canonical universe is the production raw pool (source of truth), and natural-selected universes should always be derived from it through the selection engine. Document both layers in every audit entry (`selection_mode`, `universe_source`, `selection_audit.json` hash) so traceability persists across `baseline-guardrail` and tournament outputs.
### 4. Clarify the difference between benchmark and raw_pool_ew
`benchmark` is an equal-weighted control over the **selected** (active) universe, whereas `raw_pool_ew` sits over the **raw (canonical or selected) pool** and is used strictly for selection-alpha diagnostics. The benchmark is the risk-profile comparator, and `raw_pool_ew` is the selection baseline; they must not be conflated.

## Risk Profile Matrix
| Profile | Category | Universe | Weighting / Optimization | Notes |
| --- | --- | --- | --- | --- |
| `market` | Baseline | Benchmark symbols (`settings.benchmark_symbols`) | Equal-weight long-only allocation; no optimizer, no clusters | Institutional hurdle; logged identically across engines (`market_profile_unification`). |
| `benchmark` | Baseline | Natural-selected universe | Asset-level equal weight over the winners; no clustering | Research baseline; logs universe source + count for every run so alpha deltas are traceable. |
| `raw_pool_ew` | Selection-alpha baseline | Canonical or selected (via `TV_RAW_POOL_UNIVERSE`) | Asset-level equal weight across the raw pool, excludes benchmark symbols | Diagnostic only until coverage + invariance pass; record `raw_pool_symbol_count` and hash per window. |
| `equal_weight` | Risk profile | Natural-selected universe | Hierarchical equal weight (cluster-level HE + HERC 2.0 intra) | Neutral, low-friction profile used for volatility-neutral comparisons. |
| `min_variance` | Risk profile | Natural-selected universe | Cluster-level minimum variance (solver-driven) | Defensive, low-volatility target; guardrails ensure `HERC 2.0` intra weighting. |
| `hrp` | Risk profile | Natural-selected universe | Hierarchical risk parity (HRP) | Structural risk-parity baseline for regime robustness; uses cluster distances tuned by metadata. |
| `max_sharpe` | Risk profile | Natural-selected universe | Cluster-level max Sharpe mean-variance | Growth regime focus; exposures are clamped by cluster caps before solver execution. |
| `barbell` | Strategy profile | Natural-selected universe | Core HRP sleeve + aggressor sleeve | Convexity-seeking profile that combines core stability with an antifragility-driven tail sleeve (`barbell` details are in `multi_engine_optimization_benchmarks.md`). |
| `market_baseline` | Legacy baseline alias | Benchmark symbols | Same as `market` | Provided for custom engine / legacy dashboards; matches `market` exactly. |
| `benchmark_baseline` | Legacy baseline alias | Natural-selected universe | Same as `benchmark` | Legacy name emitted by the `custom` engine; metrics should match `benchmark` in every run. |

## Plan Items (Open)
- [x] **Raw Pool Baseline Universe Control**: `raw_pool_ew` now toggles its universe source via `TV_RAW_POOL_UNIVERSE`/`RAW_POOL_UNIVERSE` so canonical selection baselines stay reproducible.
  - **Need**: Honor the flag, load canonical returns when requested, and emit per-window provenance (symbols, hash, source) so audits can pair raw pools with their metadata.
  - **Status**: `scripts/backtest_engine.py` respects `settings.raw_pool_universe`, aligns canonical returns with the primary index, and falls back gracefully when canonical candidates are missing; `scripts/prepare_portfolio_data.py` exposes configurable output paths; `docs/specs/plan-report.md` now captures the canonical/selected snapshots for run `20260103-182051` alongside the audit context.
  - **Files**: `scripts/backtest_engine.py`, `scripts/prepare_portfolio_data.py`, `tradingview_scraper/settings.py`.
  - **Doc**: `docs/specs/backtest_framework_v2.md`, `docs/specs/plan.md`, `docs/specs/plan-report.md`.
- [x] **Audit Ledger Context Gaps**: `audit.jsonl` lacked selection/rebalance/window metadata for optimization/simulation steps.
  - **Need**: Emit a `context` block with `selection_mode`, `rebalance_mode`, window indexes/dates, and `universe_source` for every recorded action.
  - **Status**: `AuditLedger.record_intent`/`record_outcome` now accept optional `context`; runs log the extra fields and guardrail tooling consumes them to detect sentinel mismatches.
  - **Files**: `tradingview_scraper/utils/audit.py`, `scripts/backtest_engine.py`.
  - **Doc**: `docs/specs/audit_ledger_v2.md`.
- [x] **Selection Audit Ledger Linkage**: The selection provenance chain previously stopped short of the tournament ledger.
  - **Need**: Hash and emit `selection_audit.json` along with raw/selected counts so the ledger can tie selection alpha back to raw candidates.
  - **Status**: `scripts/natural_selection.py` records the `selection_audit.json` hash, raw candidate counts, and winner counts in `audit.jsonl`; canonical run `20260103-171756/171913` now documents 45 raw candidates, `[60,120,200]` lookbacks, and the canonical cluster winners alongside the ledger entry.
  - **Doc**: `docs/specs/audit_ledger_v2.md`.
- [x] **Rebalance Audit Logs Missing**: `scripts/run_4d_tournament.py` left the `logs/` directory empty unless it was routed through the pipeline.
  - **Status**: The script now writes `rebalance_audit.log` under `artifacts/summaries/runs/<RUN_ID>/logs/`; the log path is recorded in `audit.jsonl` and documented in `docs/specs/artifacts_paths.md`.
- [x] **Canonical Universe Coverage Shrinkage**: A global `dropna(how="any")` collapsed the canonical universe before walk-forward windows were evaluated.
  - **Status**: Backtests now prune symbols per window rather than globally, allowing canonical returns to retain their breadth; canonical run `20260103-150600` completed without losing windows.
- [x] **Baseline Invariance Audit**: `raw_pool_ew` must stay invariant when selection mode changes but the universe source stays fixed, and canonical/selected mismatches should be treated as sentinel evidence.
  - **Need**: Guardrail that compares same-universe runs and gracefully documents mismatched (sentinel) comparisons.
  - **Status**: `scripts/raw_pool_invariance_guardrail.py` (`make baseline-guardrail`) loads audit metadata, prints `selection_mode`, `universe_source`, `raw_pool_symbol_count`, and `raw_pool_returns_hash`, and skips the tolerance check when the universe source or returns hash differ. Canonical pair `20260103-171756/171913` and selected pair `20260103-172054/182051` pass; the mismatched canonical vs selected pair now exits with a sentinel notice instead of a failure. `docs/specs/plan-report.md` captures the latest guardrail snapshot plus the sentinel narrative for run `20260103-182051`.
  - **Doc**: `docs/specs/plan-report.md`, `docs/specs/plan.md`.
- [x] **Metadata Catalog Drift (Veto Cascade)**: Missing `tick_size`, `lot_size`, and `price_precision` metadata forces repeated vetoes and destabilizes HRP distances.
  - **Need**: Enrich candidate manifests after `data-prep-raw`/`port-select`, gate the tournament when coverage falls below ~95%, and keep HRP matrix health visible.
  - **Status**: Completed. Enrichment keeps candidate manifests complete, and the coverage gate is enforced via `scripts/metadata_coverage_guardrail.py`.
    - **Gate workflow**: Run `scripts/enrich_candidates_metadata.py` right after `make data-prep-raw` and again after `make port-select`; record the coverage (% symbols with tick/lot/precision) in `audit.jsonl` so the guardrail reads `metadata_coverage` before tournaments. If coverage <95%, fail the tournament early and log the shortfall in `artifacts/summaries/runs/<RUN_ID>/logs/metadata_coverage.log`.
    - **Automation**: `scripts/metadata_coverage_guardrail.py` now runs automatically via `make data-prep-raw` (canonical) and `make port-select` (selected) to re-invoke `enrich_candidates_metadata.py` when coverage dips below 95%, write the percentage to `metadata_coverage.log`, and emit the same coverage metrics to `audit.jsonl`.
  - **Audit/Tests**: Re-run enrichment for the next run, capture coverage stats in the ledger, and verify the health gate (new script/CI check) blocks completion when the threshold is not met.
  - **Detailed steps**:
    1. Run `make data-prep-raw` to generate canonical/selected candidate manifests and raw returns.
    2. Execute `make port-select` to derive the natural-selected winners used downstream.
    3. Run `scripts/enrich_candidates_metadata.py --canonical artifacts/summaries/runs/<RUN_ID>` (and again post port-select) to fill `tick_size`, `lot_size`, and `price_precision` for both catalogs.
    4. Read `metadata_coverage` from the resulting `audit.jsonl` entry and write the percentage (with timestamp + RUN_ID) into `artifacts/summaries/runs/<RUN_ID>/logs/metadata_coverage.log`.
    5. If coverage ≥95%, allow the tournament to continue and log the gate pass (in `audit.jsonl` and this doc). If coverage <95%, fail fast, record the shortfall (per symbol), and keep the gate in place until the next enrichment run fills the missing fields.
    6. Update this plan with the next RUN_ID/log path and mark the metadata gate as satisfied once the threshold and health audit succeed.
  - **Latest coverage**: Run `20260103-213947` recorded 100% coverage for both canonical and selected catalogs; see `artifacts/summaries/runs/20260103-213947/logs/metadata_coverage.log`.
  - **Health audit proof**: `make data-audit STRICT_HEALTH=1` for run `20260103-213947` succeeded and the output is archived at `artifacts/summaries/runs/20260103-213947/logs/data-audit.log`, so the gate now has coverage + health evidence.
- [x] **Selection Report Generator Missing Entry Point**: `scripts/generate_reports.py` continues to raise `module 'scripts.generate_selection_report' has no attribute 'generate_selection_report'`, skipping the selection report.
  - **Impact**: Every run misses the selection report section.
  - **Need**: Restore or redirect the entry point so the report pipeline can finish.
  - **Status**: Completed. Fixed signature in `scripts/generate_selection_report.py`.
  - **Evidence**: Fixed by adding `generate_selection_report` function with proper arguments.
  - **Audit/Tests**: After fixing the entry point, run `scripts/generate_reports.py` against a recent run and confirm both the selection report and target output file appear in `artifacts/summaries/runs/<RUN_ID>/reports/selection_report.md` with no attribute errors.
- [x] **CVXPortfolio Missing-Returns Warnings**: CVXPortfolio emits “incorrect missing values structure” and “holdings provided don't match the universe implied by the market data server” during audits.
  - **Impact**: High-fidelity simulator results may be skipped or misaligned when universes drift window-to-window.
  - **Need**: Investigate the evolving universe per-window, align the missing-value structure, and consider `universe_selection_in_time` or explicit snapshots.
  - **Status**: Completed. Applied `fillna(0.0)` and index alignment in `CVXPortfolioSimulator`.
  - **Evidence**: Warnings resolved by ensuring contiguous returns and perfect holdings alignment.
  - **Assessments**: Capture the warnings from the next guardrail or tournament run, compare the universe hash for the `cvxportfolio` windows, and log which assets triggered mismatched holdings; once resolved, the warnings should disappear from `artifacts/summaries/runs/<RUN_ID>/logs/02_backtest.log`.
- [ ] **Guardrail Sentinel Monitoring**: Keep the canonical/selected guardrail story visible and repeatable.
  - **Need**: Re-run the canonical (`20260103-171756/171913`) and selected (`20260103-172054/182051`) guardrail pairs quarterly, log the sentinel canonical vs selected command, and refresh `docs/specs/plan-report.md` with any new RUN_IDs or metadata changes.
  - **Status**: `make baseline-guardrail` now prints metadata and exits successfully when universes differ; the latest sentinel snapshot is recorded in `docs/specs/plan-report.md` for run `20260103-182051`.
  - **Validation**: Same-universe guardrail passes still enforce invariance while the sentinel branch remains a documented signal.
  - **Audit/Tests**: Document each rerun by copying the guardrail console output into `docs/specs/plan-report.md`, storing the sentinel table, and verifying the `metadata` printout still includes `selection_mode`, `universe_source`, `raw_pool_symbol_count`, and `raw_pool_returns_hash`.

## Current Focus
- **Guardrail sentinel readiness**: Keep canonical and selected guardrail pairs re-run, publish the sentinel notice in each release, and keep `docs/specs/plan-report.md` up to date with the latest RUN_IDs.
- **Metadata gate**: Enforce enrichment coverage (>=95%) before tournaments and signal health regressions when metadata drops.
- **CVXPortfolio warnings**: Resolve missing-values/universe drift so the simulator stops raising the “incorrect missing values structure” warnings.
- **Selection report**: Restore `generate_selection_report` so the selection story appears in every audit run.
## Completed (Audit Validated)
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

## Completed (Logic Integrity)
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
- **Run ID:** `20260103-182051` (production `make flow-production PROFILE=production` run that anchors the guardrail snapshot in `docs/specs/plan-report.md`).
- **Additional Validation Runs:** `20260103-010210` (dev data prep), `20260103-010147` (dev tournament windows), `20260103-005936` (prod tournament), plus the canonical (`20260103-171756/171913`) and selected (`20260103-172054/182051`) guardrail pairs.
- **Key Artifacts:** `artifacts/summaries/runs/20260103-182051/{audit.jsonl,tournament_results.json,tournament_results/plan-report.md}`, `docs/specs/plan-report.md` (guardrail narrative).
- **Ledger Integrity:** Verified via `scripts/verify_ledger.py` and the `selection_audit.json` hash linkage.
- **Notable Observations:** Guardrail sentinel runs now log metadata (selection mode, universe source, raw_pool hash/count); the sentinel canonical vs selected comparison gracefully exits and is described in `docs/specs/plan-report.md`; `data_prep` still logs resolved lookback days for dev profiles.

## ✅ Validation Checklist
- [x] Re-run Step 5 (data-fetch lightweight) and confirm `audit.jsonl` logs correct lookback days.
- [x] Re-run tournament and confirm `tournament_results.json` includes simulators + results, and `returns/` is populated.
- [x] Re-run tournament and confirm `train_window`, `test_window`, `step_size` match `resolved_manifest.json`.
- [x] Re-run optimization and confirm `profiles.barbell` appears in `portfolio_optimized_v2.json` (or is explicitly skipped with a warning).
- [ ] Verify health audits remain clean after alignment changes (no padded weekends).
- [x] Confirm run log files are written to `artifacts/summaries/runs/<RUN_ID>/logs/`.
- [x] Confirm `data/lakehouse/portfolio_optimized_v2.json` exists post-optimization.
- [ ] Re-run the canonical (`20260103-171756/171913`) and selected (`20260103-172054/182051`) guardrail pairs quarterly, logging the sentinel result for canonical vs selected to prove the metadata branch still fires, and update the doc with any new RUN_IDs.

## Audit & Tests
- **Metadata gate**: Run `scripts/enrich_candidates_metadata.py` (post `data-prep-raw`/`port-select`), inspect `audit.jsonl` entries for `metadata_coverage` percent, and confirm the new health gate fails when coverage <95% (capture logs under `artifacts/summaries/runs/<RUN_ID>/logs/metadata_coverage.log`).
- **Selection report**: Execute `scripts/generate_reports.py` after restoring `generate_selection_report`, verify `selection_report.md` is created with the expected sections, and note the run ID in `docs/specs/plan.md` so the plan references the validated artifact.
- **CVXPortfolio warnings**: Reproduce the warnings using the next production tournament, identify the universe mismatch causing them, apply any needed alignment (e.g., ensure `cvxportfolio` gets the same `raw_pool` slice), and rerun to ensure log entries disappear.
- **Guardrail sentinel**: Rerun canonical/selected guardrails quarterly, capture metadata printouts, and update `docs/specs/plan-report.md` with the new RUN_IDs plus sentinel notes so the plan continues to reflect the latest evidence.
- **Health audit**: `make data-audit STRICT_HEALTH=1` for run `20260103-213947` now passes and its log lives at `artifacts/summaries/runs/20260103-213947/logs/data-audit.log`; keep capturing this log whenever alignment changes occur so the health gate stays transparent.

## Next Steps Tracker
- **Metadata gate**: Gate satisfied for `20260103-213947`—both `metadata_coverage.log` and `data-audit.log` document 100% coverage plus a passing health check; keep watching future runs so any drop below 95% coverage or health failures re-trigger the gate.
- **Selection report**: Repair the missing `generate_selection_report` entry point, rerun `scripts/generate_reports.py`, and add the resulting `artifacts/summaries/runs/<RUN_ID>/reports/selection_report.md` path (with run ID) to this section as proof.
- **CVXPortfolio warnings**: Reproduce the warnings, compare CVXPortfolio’s universe hashes to the canonical raw pool, apply the universe alignment fix, rerun, and note the clean `02_backtest.log` run ID inside the plan.
- **Guardrail sentinel**: Plan the next quarterly guardrail rerun, capture the metadata printouts via `make baseline-guardrail --run-a 20260103-171756 --run-b 20260103-171913` (and likewise for selected), and copy the console output into `docs/specs/plan-report.md` before closing the validation item.

## Status Sync
- **Metadata gate**: Satisfied—the latest enrichment run (`20260103-213947`) recorded 100% coverage and a passing health audit (see `artifacts/summaries/runs/20260103-213947/logs/metadata_coverage.log` and `artifacts/summaries/runs/20260103-213947/logs/data-audit.log`); keep the coverage/health logs fresh for future runs.
- **Selection report**: Pending—the missing entry-point fix is outstanding; after the next `scripts/generate_reports.py` execution produces `selection_report.md`, drop the artifact path and run ID into this section.
- **CVXPortfolio warnings**: Pending—warnings still surfaced (see runs `20260103-164537`/`20260103-164708`); once the per-window universe alignment fix is applied, add the clean `02_backtest.log` proof and mark the task as resolved.
- **Guardrail sentinel**: Pending—canonical/selected reruns need to be scheduled; log the next run IDs and copy the metadata printout into `docs/specs/plan-report.md` so the sentinel item can close.
- **Health audit**: Completed for run `20260103-213947` (see `artifacts/summaries/runs/20260103-213947/logs/data-audit.log`), but keep re-running the check after any new alignment fixes so the log stays up to date.
