# Implementation Plan: Async Streamer Feature Parity
**Track ID**: `async_streamer_parity_20251221`
**Status**: Planned

## 1. Objective
Achieve 100% logic parity between the legacy synchronous `Streamer` and the new `AsyncStreamer`, specifically regarding data serialization, structured output, and file export.

## 2. Phases

### Phase 1: Data Serialization Parity
Goal: Transform raw WebSocket packets into structured dictionaries.
- [x] Task: Implement OHLC and Indicator serialization logic in `AsyncStreamer`. 51a91cb
- [ ] Task: Update `get_data()` to yield formatted data.
- [ ] Task: Verify parity via unit tests comparing sync/async dictionary output.

### Phase 2: Functional Parity
Goal: Implement one-shot collection and export.
- [ ] Task: Implement `export_result` support (persistence to JSON/CSV).
- [ ] Task: Implement `collect(n_candles)` helper method for batch retrieval.

### Phase 3: Structural Consolidation
Goal: Clean up duplicate logic.
- [ ] Task: Move shared parsing logic to `tradingview_scraper/symbols/stream/utils.py`.
- [ ] Task: Refactor both screeners to use centralized utilities.

### Phase 4: Validation
- [ ] Task: Final parity audit and benchmark.
- [ ] Task: Final Report.
