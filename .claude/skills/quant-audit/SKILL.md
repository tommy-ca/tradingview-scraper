---
name: quant-audit
description: Verify Lakehouse integrity and data health. Use to identify "toxic" assets, stale data, and schema drift.
compatibility: Claude Code
metadata:
  author: quant-team
  version: "1.0"
  category: DataOps
allowed-tools: Bash(python:*) Bash(make:*) Read
---

# Quant Audit (Data Health)

Verify the integrity and health of the historical market data stored in the Lakehouse.

## When to use this skill

Use this skill when you want to:
- Check for "toxic" assets (high NaN density)
- Verify that all ingested Parquet files are valid
- Audit the coverage between returns and features matrices
- Identify stale data files

## How to run

1. **Run the data audit**:
   ```bash
   make data-audit
   ```

2. **Check the health registry**:
   ```bash
   cat data/lakehouse/foundation_health.json | jq
   ```

## Output

The audit will report:
- Total number of symbols tracked
- Count of healthy vs toxic assets
- Any missing or stale files
