# Metadata Catalog Schema and Usage Guidelines

## Overview

This document describes the metadata catalog system for TradingView scraper, which manages instrument definitions for exchanges and symbols in the data lakehouse.

## Architecture

### Components

1. **MetadataCatalog** (`data/lakehouse/symbols.parquet`)
   - Symbol-level metadata with SCD Type 2 versioning
   - Point-in-time (PIT) lookup capabilities
   - Change detection and validation

2. **ExchangeCatalog** (`data/lakehouse/exchanges.parquet`)
   - Exchange-level metadata and defaults
   - Used for timezone and market session defaults

3. **MetadataService** 
   - High-level interface for symbol discovery and resolution
   - Future support for hybrid data sources (TradingView + CCXT)

## Schema Definition

### Symbol Metadata Schema

| Field | Type | Required | Description |
|--------|------|----------|-------------|
| symbol | str | ✓ | Full symbol identifier (e.g., "BINANCE:BTCUSDT") |
| exchange | str | ✓ | Exchange name (e.g., "BINANCE", "BYBIT") |
| base | str | ✗ | Base currency (e.g., "BTC") |
| quote | str | ✗ | Quote currency (e.g., "USDT") |
| type | str | ✓ | Instrument type ("spot", "swap", "futures", "stock", "forex") |
| subtype | str | ✗ | Additional classification (e.g., "perpetual") |
| description | str | ✗ | Human-readable description |
| sector | str | ✗ | Economic sector (for stocks) |
| industry | str | ✗ | Industry classification (for stocks) |
| country | str | ✗ | Country/region of exchange |
| pricescale | int | ✓ | Price precision (decimal places) |
| minmov | int | ✓ | Minimum price movement |
| tick_size | float | ✗ | Calculated tick size (minmov / pricescale) |
| lot_size | float | ✗ | Contract lot size (for execution) |
| contract_size | float | ✗ | Contract size (for execution) |
| timezone | str | ✓ | Exchange timezone (e.g., "UTC", "America/New_York") |
| session | str | ✗ | Trading session ("24x7", "09:30-16:00", etc.) |
| active | bool | ✓ | Currently active instrument |
| valid_from | datetime | ✓ | Record validity start (SCD Type 2) |
| valid_until | datetime | ✗ | Record validity end (null = currently active) |
| updated_at | datetime | ✓ | Last update timestamp |

### Exchange Metadata Schema

| Field | Type | Required | Description |
|--------|------|----------|-------------|
| exchange | str | ✓ | Exchange identifier |
| country | str | ✓ | Country/region |
| timezone | str | ✓ | Primary timezone |
| is_crypto | bool | ✓ | Crypto exchange flag |
| description | str | ✓ | Exchange description |
| updated_at | datetime | ✓ | Last update timestamp |

## Data Flow

### Building Catalog

```python
# Using build script
uv run python scripts/build_metadata_catalog.py \
    --config configs/crypto_cex_binance_top50.yaml \
    --limit 100

# Or specific symbols
uv run python scripts/build_metadata_catalog.py \
    --symbols BINANCE:BTCUSDT BYBIT:ETHUSDT
```

### Auditing Catalog

```python
# Full audit
uv run python scripts/audit_metadata_catalog.py

# Timezone audit
uv run python scripts/audit_metadata_timezones.py

# Point-in-time audit
uv run python scripts/audit_metadata_pit.py
```

### Cleaning Catalog

```python
# Fix data types and duplicates
uv run python scripts/cleanup_metadata_catalog.py
```

## Usage Examples

### Basic Symbol Lookup

```python
from tradingview_scraper.symbols.stream.metadata import MetadataCatalog

catalog = MetadataCatalog()
metadata = catalog.get_instrument("BINANCE:BTCUSDT")

if metadata:
    print(f"Tick size: {metadata['tick_size']}")
    print(f"Timezone: {metadata['timezone']}")
```

### Point-in-Time Lookup

```python
from datetime import datetime
from tradingview_scraper.symbols.stream.metadata import MetadataCatalog

catalog = MetadataCatalog()
# Get metadata as of yesterday
yesterday = datetime.now().replace(hour=0, minute=0, second=0)
historical_meta = catalog.get_instrument("BINANCE:BTCUSDT", as_of=yesterday)
```

### Exchange Metadata

```python
from tradingview_scraper.symbols.stream.metadata import ExchangeCatalog

ex_catalog = ExchangeCatalog()
exchange_info = ex_catalog.get_exchange("BINANCE")

if exchange_info:
    print(f"Timezone: {exchange_info['timezone']}")
    print(f"Is Crypto: {exchange_info['is_crypto']}")
```

## Validation Rules

### Symbol Validation

1. **Required Fields**: symbol, exchange, type must be present and non-empty
2. **Numeric Fields**: pricescale, minmov must be positive integers
3. **Tick Size**: Calculated as minmov / pricescale, must be positive
4. **Timezone**: Must be valid IANA timezone or "UTC"
5. **Session**: Must be valid session pattern or "24x7" for crypto

### Exchange Validation

1. **Required Fields**: exchange, country, timezone must be present
2. **Timezone**: Must be valid IANA timezone
3. **Unique**: Exchange names must be unique

## Best Practices

### 1. Data Consistency

- Always use proper data types (int for pricescale/minmov)
- Validate timezone names against IANA database
- Use consistent exchange names across symbols and exchange catalog

### 2. Change Detection

- Only update records when critical fields change
- Maintain SCD Type 2 versioning for audit trail
- Include timestamps for change tracking

### 3. Performance

- Use point-in-time lookups for historical queries
- Index catalog on symbol and valid_from/valid_until fields
- Cache frequently accessed exchange metadata

### 4. Error Handling

- Validate input data before processing
- Log warnings for non-critical issues
- Skip records with critical validation errors

## Maintenance Schedule

### Daily
- Run audit scripts to check for inconsistencies
- Update active symbols with latest TradingView data

### Weekly  
- Clean up duplicate records
- Validate timezone and session data
- Update exchange metadata if needed

### Monthly
- Review and archive old inactive records
- Update exchange metadata defaults
- Performance optimization and indexing review

## Integration Points

### Data Lakehouse
- Catalog files stored in `data/lakehouse/` directory
- Parquet format for efficient querying
- Compatible with pandas and pyarrow

### TradingView API
- Symbol metadata fetched via Overview API
- Exchange metadata uses default configuration
- Real-time validation against API responses

### Future CCXT Integration
- MetadataService designed for hybrid sourcing
- Exchange metadata can be enriched with CCXT data
- Symbol discovery across multiple exchanges

## Troubleshooting

### Common Issues

1. **Type Mismatches**: Run cleanup script to fix data types
2. **Missing Timezones**: Check exchange metadata defaults  
3. **Duplicate Symbols**: Use cleanup script to remove duplicates
4. **Invalid Tick Sizes**: Recalculate with cleanup script

### Debug Commands

```python
# Check catalog health
python scripts/audit_metadata_catalog.py

# Validate specific symbol
python scripts/validate_symbol.py BINANCE:BTCUSDT

# Rebuild from scratch
rm data/lakehouse/symbols.parquet
python scripts/build_metadata_catalog.py --config your_config.yaml
```

## Schema Evolution

### Versioning
- Schema changes should maintain backward compatibility
- New fields added with nullable types initially
- Document breaking changes in release notes

### Migration
- Use cleanup scripts for data type changes
- Implement gradual rollouts for new features
- Maintain archive of old catalog versions