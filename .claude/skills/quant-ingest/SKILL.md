---
name: quant-ingest
description: Ingest new symbols from providers (e.g., Binance). Use when you need to fetch historical OHLCV data for new assets or update existing ones.
compatibility: Claude Code
metadata:
  author: quant-team
  version: "1.0"
  category: DataOps
allowed-tools: Bash(python:*) Bash(make:*) Read
---

# Quant Ingest (Data Fetch)

Fetch historical market data (OHLCV) from exchanges and store it in the Lakehouse (Parquet format).

## When to use this skill

Use this skill when you need to:
- Ingest data for a new list of symbols
- Update historical data for existing assets
- Fetch data for a specific profile (e.g., `crypto_production`)

## Arguments

The skill accepts a profile name or defaults to the standard fetch target:

- `crypto_production` - Fetch Binance spot assets
- `binance_spot` - Fetch all Binance spot assets

## How to run

1. **Run the data fetch**:
   ```bash
   make data-fetch PROFILE=$ARGUMENTS
   ```

2. **Verify ingestion**:
   - Check `data/lakehouse/` for new `.parquet` files.
   - Run `make data-audit` to verify integrity.

## Example usage

User: "Ingest Binance spot data"
→ Execute: `make data-fetch PROFILE=binance_spot`
