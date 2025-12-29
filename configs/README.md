# Workflow Configuration Manifests

This directory contains environment-based configuration manifests for various workflows.

## Manifest Files

- **`daily_production.env`**: The institutional daily production settings. Focuses on deep history (200d), high-integrity backfills, and all optimization engines.
- **`repro_dev.env`**: A lightweight configuration for testing the pipeline end-to-end. Faster scans, shorter history (40d), and reduced symbol counts.

## Usage

Use the `MANIFEST` variable with `make` to switch between profiles:

```bash
# Run the daily production pipeline
make daily-run MANIFEST=configs/daily_production.env

# Run a quick development smoke-test
make daily-run MANIFEST=configs/repro_dev.env
```

## Reproducibility

To ensure a specific run is perfectly reproducible:
1. Fix the `TV_RUN_ID` in the manifest.
2. Ensure `PORTFOLIO_BACKFILL=0` if using cached data, or `PORTFOLIO_BACKFILL=1` for fresh data.
3. Commit the manifest along with the code.

## Variables

| Variable | Description |
| :--- | :--- |
| `TV_RUN_ID` | Scopes all artifacts to a specific directory. |
| `PORTFOLIO_LOOKBACK_DAYS` | Days of history to fetch. |
| `TOP_N` | Assets to select per cluster. |
| `CLUSTER_CAP` | Max weight per hierarchical risk bucket. |
| `BACKTEST_TRAIN` | Training window for walk-forward validation. |
| `GIST_ID` | GitHub Gist for artifact publishing. |
