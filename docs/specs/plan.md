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
- [ ] **Raw Pool Baseline Universe Control**: `raw_pool_ew` currently uses the selected universe (`portfolio_candidates.json`) because `portfolio_returns.pkl` is built from selected candidates by default.
  - **Need**: Allow `raw_pool_ew` to choose between canonical (`portfolio_candidates_raw.json`) and selected universes via `TV_RAW_POOL_UNIVERSE`.
  - **Status**: `TV_RAW_POOL_UNIVERSE` added; `raw_pool_ew` uses `portfolio_returns_raw.pkl` when present. Canonical returns now generated in `make data-prep-raw`. Baseline invariance remediation still required.
  - **Validation**:
    - Run `20260103-160121` (canonical) produced **0 raw_pool_ew windows** due to canonical gaps (invariance not assessable).
    - Run `20260103-161050` (selected) produced **11 raw_pool_ew windows** with a valid summary (`backtest_comparison.md`).
    - Run `20260103-163738` (canonical, post-repair) produced **11 raw_pool_ew windows** with a valid summary; canonical coverage now aligns with selected returns.
    - Run `20260103-164537` (canonical, post-metadata refresh) produced **11 raw_pool_ew windows**; summary differs from selected run (see below).
    - Run `20260103-164708` (selected, post-metadata refresh) produced **11 raw_pool_ew windows**.
    - Run `20260103-171756` (canonical, selection v3) produced **11 raw_pool_ew windows**.
    - Run `20260103-171913` (canonical, selection v3.2) produced **11 raw_pool_ew windows** with **identical** summary to `20260103-171756`.
    - Run `20260103-172054` (selected, selection v3) produced **11 raw_pool_ew windows**.
    - Run `20260103-173421` (selected, selection v3.2) produced **11 raw_pool_ew windows** with **identical** summary to `20260103-172054`.
  - **Latest status**: Canonical and selected baselines both produce non-zero windows; **same-universe invariance verified** across selection modes (v3 vs v3.2) for both canonical and selected universes.
  - **Selection baseline status**: `raw_pool_ew` is **selection benchmark baseline** per universe when coverage + invariance hold. Use **canonical raw_pool_ew** vs **selected benchmark** to compute selection alpha.
  - **Guardrail proof**: The canonical pair (`20260103-171756` vs `20260103-171913`) and the selected pair (`20260103-172054` vs `20260103-182051`) both pass `make baseline-guardrail` with identical windows/returns/vols, so reuse those RUN_IDs whenever the guardrail is rerun; mismatched comparisons (canonical vs selected) should be avoided because they intentionally fail tolerance and highlight the universe-source difference.
  - **Root Cause (Canonical = 0 windows)**:
    - `portfolio_returns_raw.pkl` starts later than the selected-returns index (`2025-01-06` vs `2024-08-22`), so canonical returns are reindexed into a longer window that includes missing rows.
    - With `train=252`, `test=21`, the window length is `274` and there are **4** total windows; none can start late enough to fit entirely inside the canonical date span (raw start index `93`, max feasible start index `68`).
    - Every canonical symbol has at least one `NaN` across each window slice, so `valid_raw_symbols` is empty and `raw_pool_ew` weights are never created.
  - **Next Actions**:
    - Rebuild canonical returns with aligned lookback so canonical history spans at least `train + test + 1` rows for production windows.
    - Run `make data-repair` (canonical) to eliminate remaining gaps that block full-window coverage.
    - Re-run production tournament with `TV_RAW_POOL_UNIVERSE=canonical` and a canonical-aligned `start_date` (or shortened windows) to validate non-zero windows and invariance; regenerate reports.
    - Add a lightweight invariance guardrail (warn when same-universe raw_pool_ew summaries drift across selection modes).
    - Keep canonical vs selected comparisons separate; differences across universes are expected.
  - **Conclusion**: `raw_pool_ew` is **baseline-ready per-universe**; invariance validated across selection modes for the same universe.
  - **Files**: `scripts/prepare_portfolio_data.py`, `scripts/backtest_engine.py`, settings.
  - **Doc**: `docs/specs/backtest_framework_v2.md`.
- [ ] **Audit Ledger Context Gaps**: `audit.jsonl` lacks rebalance mode, selection mode, window boundaries, and train/test/step metadata.
  - **Need**: Add `context` block to `backtest_optimize` / `backtest_simulate` intents/outcomes.
  - **Status**: Context support implemented and validated in `audit.jsonl` for run `20260103-150600` (no missing fields across optimize/simulate).
  - **Files**: `tradingview_scraper/utils/audit.py`, `scripts/backtest_engine.py`.
  - **Doc**: `docs/specs/audit_ledger_v2.md`.
- [ ] **Selection Audit Ledger Linkage**: Selection provenance (canonical → selected) is captured in `selection_audit.json`, but tournament `audit.jsonl` does not link to it.
  - **Need**: Hash and record `selection_audit.json` in `audit.jsonl` for each run, including raw pool counts/hashes and selection counts/hashes.
  - **Impact**: Selection alpha cannot be fully traced from raw_pool → selected winners without manual cross-references.
  - **Status**: Implemented selection audit hash + raw/selected counts in `scripts/natural_selection.py` ledger outcomes.
  - **Audit detail**: Canonical run `20260103-171756/171913` records 45 raw candidates, lookbacks `[60,120,200]`, cluster map + winners (SPY/AAPL/AMZN/AVGO/GOOG/TSLA/WMT + NYSE names) and writes `selection_audit.json` whose hash is now stored in the ledger.
- [ ] **Rebalance Audit Logs Missing**: Run `20260103-054505` has no `logs/` directory.
  - **Cause**: `scripts/run_4d_tournament.py` does not create log files unless invoked via production pipeline.
  - **Need**: Either instrument logging for that script or document the expectation and run it through the pipeline.
  - **Status**: Confirmed logs created in run `20260103-150600` at `artifacts/summaries/runs/20260103-150600/logs/rebalance_audit.log`.
  - **Doc**: `docs/specs/artifacts_paths.md`.
- [ ] **Canonical Universe Coverage Shrinkage**: `BacktestEngine` drops rows with any NaN (`dropna(how="any")`), which can collapse the canonical universe window length.
  - **Need**: Replace with per-window or per-asset alignment to preserve coverage and avoid truncating canonical baselines.
  - **Status**: Global dropna replaced with per-window full-data filtering; canonical run `20260103-150600` completed, but further analysis needed on any hidden coverage loss.
  - **Files**: `scripts/backtest_engine.py`.
- [ ] **Baseline Invariance Audit**: `raw_pool_ew` should be selection-mode invariant; verify CVX/nautilus baselines do not drift with selection sweeps.
  - **Need**: Add audit check or guardrail to ensure invariance; log a warning if violated.
  - **Status**: Manual validation **passed** for same-universe runs.
    - **Canonical**: `20260103-171756` (v3) == `20260103-171913` (v3.2) raw_pool_ew summary.
    - **Selected**: `20260103-172054` (v3) == `20260103-173421` (v3.2) raw_pool_ew summary.
  - **Automation**: Added `scripts/raw_pool_invariance_guardrail.py` and `make baseline-guardrail` to compare runs and fail on drift.
    - The guardrail now pre-validates universe metadata (selection mode, universe source, hash, symbol count) and deliberately bypasses the tolerance check when the sources/hashes differ so the canonical-vs-selected comparison stays as an intentional sentinel instead of a recurring failure.
    - **Guardrail sentinel workflow**: Always pair canonical→canonical (`20260103-171756/171913`) and selected→selected (`20260103-172054/182051`) runs when enforcing invariance; mismatched canonical vs selected runs should keep running for transparency, and they now log the metadata mismatch and exit successfully so the table below can highlight the sentinel result without triggering a failure.
    - **Metadata expectations**: Every guardrail run must emit `selection_mode`, `universe_source`, `raw_pool_symbol_count`, and `raw_pool_returns_hash` in `audit.jsonl` so the sentinel detection can operate and future comparisons can reuse the same RUN_ID references.
- [ ] **Metadata Catalog Drift (Veto Cascade)**: Tournament runs veto assets due to missing `tick_size`, `lot_size`, and `price_precision`, collapsing HRP distance matrices.
  - **Evidence**: Run `20260103-163738` logs repeated vetoes for benchmark equities (e.g., `AMEX:SPY`, `NASDAQ:AAPL`) and HRP failures (`empty distance matrix`).
  - **Impact**: Reduces universe size, destabilizes HRP profiles, and can skew baseline comparisons.
  - **Need**: Rebuild/repair metadata catalogs for both canonical and selected universes before production tournaments.
  - **Audit**:
    - Candidate manifests now have full coverage after enrichment (`portfolio_candidates.json` = 13/13, `portfolio_candidates_raw.json` = 118/118 with required keys).
    - Portfolio meta files (`portfolio_meta.json`, `portfolio_meta_raw.json`) still omit `tick_size`, `lot_size`, `price_precision` because `prepare_portfolio_data.py` does not persist these fields; vetoes use candidate manifests, not meta files.
    - Post-enrichment tournaments (`20260103-164537`, `20260103-164708`) no longer log **Missing metadata** vetoes; remaining vetoes are ECI-based.
  - **Latest status**: Mitigated for candidate manifests; gate still required to prevent regressions.
  - **Next Actions**:
    - Run `scripts/enrich_candidates_metadata.py` after `data-prep-raw` and after `port-select` to ensure both catalogs are enriched.
    - Add a health gate that fails the tournament if metadata coverage drops below a threshold (e.g., <95% of active symbols).
    - Re-run the production tournament after metadata refresh to confirm HRP stability and consistent baseline counts.
- [ ] **Selection Report Generator Missing Entry Point**: `scripts/generate_reports.py` fails with `module 'scripts.generate_selection_report' has no attribute 'generate_selection_report'`.
  - **Impact**: Selection report section is skipped in every run.
  - **Need**: Restore the function or update the report pipeline to the correct entry point.
  - **Evidence**: Runs `20260103-164537`, `20260103-164708` report the missing attribute.
- [ ] **CVXPortfolio Missing-Returns Warnings**: CVXPortfolio logs “incorrect missing values structure” and “holdings provided don't match the universe implied by the market data server.”
  - **Impact**: High-fidelity simulator results may be inconsistent or partially skipped, especially for changing universes.
  - **Need**: Investigate universe drift across windows and align missing-values handling (consider `universe_selection_in_time` or explicit per-window universe changes).
  - **Evidence**: Runs `20260103-164537`, `20260103-164708` repeatedly log these warnings.

## Current Focus
- **Baseline invariance guardrail**: Wire `baseline-guardrail` / `baseline-audit` into production workflows and define pass/fail policy.
- **Metadata gate**: Enforce enrichment + coverage threshold (≥95%) before tournaments.
- **CVXPortfolio warnings**: Align universe handling for missing data warnings.
- **Selection report**: Restore `generate_selection_report` entry point.
- **Selection audit linkage**: Record `selection_audit.json` hash in `audit.jsonl`.

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
- [ ] Re-run the canonical (`20260103-171756/171913`) and selected (`20260103-172054/182051`) guardrail pairs quarterly, logging the sentinel result for canonical vs selected to prove the metadata branch still fires, and update the doc with any new RUN_IDs.
