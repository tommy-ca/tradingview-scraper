# 🎓 Lessons Learned: Tournament V2 & Multi-Engine Benchmarking

## Overview
The Tournament V2 run (Jan 2026) provided critical insights into the CARS 2.0 (v2) selection logic, multi-simulator fidelity, and the challenges of benchmarking during CRISIS regimes.

## 1. Selection Intelligence (V2 Spec)
- **Metadata dependency**: Selection Specs V2 and V3 are highly dependent on execution metadata (`tick_size`, `lot_size`, `price_precision`). Institutional assets (AAPL, QQQ) are vetoed if this metadata is missing from the lakehouse, leading to a degraded "Survival of the Fittest" pool.
- **Hierarchical Resilience**: The system successfully clusters assets even when simulators fail. Pruning logic effectively groups assets by return correlation and volatility units.
- **Condition Number Aggression**: High condition numbers ($\kappa > 10^{15}$) trigger aggressive pruning, which can inadvertently reduce the universe to a single benchmark (SPY) if not monitored.

## 2. Optimization Engine Dynamics
- **Engine Resiliency (skfolio)**: In CRISIS regimes, `skfolio` demonstrated superior resilience by using turnover penalties that actually improved realized returns over idealized frictionless returns. Friction acted as a "stabilizing brake" during high volatility.
- **Profile Performance**: During the 2025 CRISIS period, HRP (Hierarchical Risk Parity) profiles generally underperformed the BENCHMARK (SPY) due to the inclusion of highly volatile "winners" (TRUMPUSDT, DUST) that passed momentum gates but suffered in the walk-forward test window.

## 3. Simulator & Reporting Integrity
- **Bankruptcy Handling**: `cvxportfolio` may report bankruptcy if the policy value becomes negative during high-volatility test windows. The reporting engine must robustly handle these failure points.
- **Alpha Decay Calibration**: Realized decay (1.7% - 2.2%) is now accurately modeled across `cvxportfolio` and `vectorbt`.
- **Audit Chain**: The cryptographic audit ledger (`audit.jsonl`) is essential for reconstructing clusters and decisions when simulators fail.

## 4. Technical Debt & Fixes
- **Backtest Engine API**: `run_selection` return values were inconsistent (expected 2, provided 5). This has been patched but needs architectural standardization.
- **JSON Corruptions**: `selection_audit.json` occasionally fails to parse due to incomplete writes during multi-threaded runs.
- **Pathing Sensitivity**: `TV_RUN_ID` mismatches frequently cause report generation failures. The workflow should always use absolute paths or promoted `latest` symlinks.
