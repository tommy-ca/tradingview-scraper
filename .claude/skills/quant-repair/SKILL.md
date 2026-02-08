---
name: quant-repair
description: Repair historical data gaps in the Lakehouse. Use when you identify missing bars, NaNs, or inconsistent history in assets.
compatibility: Claude Code
metadata:
  author: quant-team
  version: "1.0"
  category: DataOps
allowed-tools: Bash(python:*) Bash(make:*) Read
---

# Quant Repair (Data Infill)

Repair gaps in historical market data using provider APIs or interpolation techniques.

## When to use this skill

Use this skill when:
- Assets are flagged as "toxic" due to NaN density
- Data audit reports missing bars
- You see unexpected NaNs in return streams

## How to run

1. **Run the data repair**:
   ```bash
   make data-repair
   ```

2. **Run with specific options**:
   ```bash
   python scripts/services/repair_data.py --max-fills 20
   ```

## Output

The repair process will log symbols that were successfully repaired and update the `foundation_health.json` registry.
