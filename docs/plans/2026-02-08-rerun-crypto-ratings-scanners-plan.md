---
title: "chore: Rerun Crypto Ratings Scanners & Optimization"
type: chore
date: 2026-02-08
---

# chore: Rerun Crypto Ratings Scanners & Optimization

## Overview

This plan outlines the optimization and execution of the crypto ratings scanner pipelines (`ratings_all` and `ratings_ma`). We will modernize the `FuturesUniverseSelector` to use vectorized Pandas operations for filtering, significantly reducing execution time. We will then execute the scanners for both Binance Spot and Perps across Long and Short profiles.

## Problem Statement / Motivation

The current scanner pipeline is slow due to:
1.  **Redundant Fetching**: Each strategy fetches the entire universe independently (Sequential Redundancy).
2.  **Iterative Processing**: The `FuturesUniverseSelector` iterates through thousands of assets row-by-row for filtering and parsing, which is computationally expensive (O(N) Python loop).

Optimizing the selector will improve the speed of the "Sequential" architecture without requiring a full "Snapshot" refactor, respecting the user's preference for isolation.

## Proposed Solution

We will implement a **Hybrid Optimization Strategy**:
1.  **Vectorized Filtering**: Convert the raw list-of-dicts to a Pandas DataFrame immediately. Apply Basic, Market Cap, Performance, and Strategy filters using vectorized boolean masks.
2.  **Vectorized Parsing**: Use Pandas string accessors (`.str`) to parse `base`, `quote`, and `exchange` efficiently.
3.  **Preserved Deduplication**: Maintain the complex "Fuzzy Tie-Breaker" logic (30%/50% thresholds) by iterating only over the *filtered* results (which are much smaller), or by applying a custom Numba-optimized aggregation if needed.

## Technical Approach

### Architecture

- **`FuturesUniverseSelector`**: Refactor `process_data` to instantiate a DataFrame.
- **Helper Extraction**: Isolate `_extract_base_quote` to support both scalar (for legacy parity tests) and Series inputs.

### Implementation Phases

#### Phase 1: Vectorization Refactor
- Update `FuturesUniverseSelector` to use Pandas.
- Implement vectorized `_apply_filters_vectorized`.
- Implement vectorized `_parse_metadata_vectorized`.

#### Phase 2: Parity Verification
- Create `scripts/verify_scanner_parity.py`.
- Run both "Legacy" (Iterative) and "Modern" (Vectorized) logic on a sample dataset.
- Assert strict equality of outputs.

#### Phase 3: Execution
- Run `make scan-run PROFILE=crypto_rating_all` (Spot + Perp).
- Run `make scan-run PROFILE=crypto_rating_ma` (Spot + Perp).

## Acceptance Criteria

### Functional Requirements
- [ ] Scanner output matches legacy logic (Logic Parity).
- [ ] Execution time reduced by at least 40%.
- [ ] All 8 target profiles (Spot/Perp x All/MA x Long/Short) generate valid JSONs in `data/discovery/`.

### Quality Gates
- [ ] `verify_scanner_parity.py` passes.

## Dependencies & Risks
- **Risk**: Regex differences in vectorized string parsing.
- **Mitigation**: Comprehensive unit tests for `_extract_base_quote`.

## References & Research
- `docs/brainstorms/2026-02-08-rerun-crypto-ratings-scanners-brainstorm.md`
- `tradingview_scraper/futures_universe_selector.py`
