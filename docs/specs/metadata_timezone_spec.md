# Technical Specification: Metadata Timezone & Localization
**Status**: Formalized
**Date**: 2025-12-21

## 1. Overview
Accurate timezone metadata is critical for preventing look-ahead bias in backtests and ensuring trade execution logic respects local market hours. The system employs a hierarchical resolution strategy to ensure every instrument has a valid IANA timezone.

## 2. Resolution Hierarchy
When a symbol is added or updated in the catalog, its timezone is resolved using the following priority:

1.  **TradingView API (`timezone`)**: If the primary data source provides a localized timezone (e.g., `America/New_York` for US Equities), it is used as the authoritative source.
2.  **Canonical Exchange Defaults**: If the API returns `None` (common for Crypto and Forex), the system looks up the exchange in the `DEFAULT_EXCHANGE_METADATA` map.
3.  **Global Fallback**: If neither source provides data, the system falls back to `UTC`.

## 3. Canonical Exchange Metadata
Authoritative defaults are maintained in `tradingview_scraper/symbols/stream/metadata.py`. Current coverage includes:

| Exchange | Canonical Timezone | Country | Classification |
|----------|-------------------|---------|----------------|
| BINANCE, OKX, BYBIT, BITGET | UTC | Global | Crypto |
| NASDAQ, NYSE | America/New_York | US | Equities |
| CME, CBOT, NYMEX | America/Chicago | US | Futures |
| LSE | Europe/London | UK | Equities |
| FX_IDC | UTC | Global | Forex |

## 4. Verification Procedures
Consistency is maintained via `scripts/audit_metadata_timezones.py`, which enforces the following invariant rules:
- **Crypto Rule**: All instruments with `subtype == 'crypto'` must be set to `UTC`.
- **Inheritance Rule**: Symbols must match the canonical timezone of their parent exchange unless an explicit API override exists.
- **Completeness Rule**: No active symbol may have a null or "Unknown" timezone.

## 5. Usage in Backtesting
Consumers of the `MetadataCatalog` should use the `timezone` field to:
1. Localize OHLCV timestamps.
2. Filter for active trading sessions.
3. Align multi-asset time-series data.
