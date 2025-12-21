# Implementation Plan: E2E Quantitative Orchestration & Robust Risk
**Track ID**: `e2e_quantitative_orchestration_20251221`
**Status**: Planned

## 1. Objective
Consolidate the multi-asset quantitative pipeline into a unified, high-performance Python orchestrator and enhance the risk management layer with market-regime intelligence and Bayesian shrinkage.

## 2. Phases

### Phase 1: Unified Orchestrator & Async Discovery
Goal: Transition from shell-based batching to a Python-native async architecture.
- [x] Task: Create `tradingview_scraper/pipeline.py` (Unified Orchestrator Class). 24bdb00
- [x] Task: Implement `AsyncScreener` to parallelize REST calls to TradingView. e7f267f
- [ ] Task: Migrate existing configurations to be driven by the new `Pipeline` entry point.

### Phase 2: Robust Risk & Regime Intelligence
Goal: Improve optimizer stability and adaptive capabilities.
- [ ] Task: Implement `MarketRegimeDetector` (Volatility-based switch).
- [ ] Task: Integrate **Ledoit-Wolf Shrinkage** for covariance estimation.
- [ ] Task: Update the Barbell Optimizer to adjust its "Safe Core" vs "Aggressor" split based on detected regimes.

### Phase 3: Scaling & Final Validation
Goal: Execute across the full universe and finalize the V1 architecture.
- [ ] Task: Execute full E2E run for Top 200 symbols (Crypto + Global).
- [ ] Task: Author the `Quantitative Workflow V1` final documentation.
