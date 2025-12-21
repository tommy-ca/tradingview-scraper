# Implementation Plan: Async Streamer V1
**Track ID**: `async_streamer_v1_20251221`
**Status**: Planned

## 1. Objective
Migrate the WebSocket streamer to a fully asynchronous architecture using `aiohttp`. This will enable non-blocking real-time data streaming and better integration with the async pipeline.

## 2. Phases

### Phase 1: Async WebSocket Core
Goal: Implement the low-level async connection and heartbeat logic.
- [x] Task: Create `tradingview_scraper/symbols/stream/stream_handler_async.py` (AsyncStreamHandler). fa51120
- [ ] Task: Implement background heartbeat task in `AsyncStreamHandler`.
- [ ] Task: Implement async message framing and session initialization.

### Phase 2: Async Streamer Implementation
Goal: Implement the user-facing async streamer interface.
- [ ] Task: Create `tradingview_scraper/symbols/stream/streamer_async.py` (AsyncStreamer).
- [ ] Task: Implement `.get_data()` as an async generator.
- [ ] Task: Implement `.stream()` method with parity for indicators and symbol validation.

### Phase 3: Resilience & Recovery
Goal: Ensure robust operation and state recovery.
- [ ] Task: Implement `AsyncRetryHandler` using `asyncio.sleep`.
- [ ] Task: Implement state-restoration logic (re-subscription) after reconnections.

### Phase 4: Validation
- [ ] Task: Create unit tests for `AsyncStreamHandler` and `AsyncStreamer`.
- [ ] Task: Add an async stream example to `examples/`.
- [ ] Task: Final Report.
