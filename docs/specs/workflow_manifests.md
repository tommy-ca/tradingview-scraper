# Specification: Workflow Configuration Manifests

This document defines the architecture and usage of the JSON-based workflow manifest system, designed to ensure institutional reproducibility and type-safety for multi-asset quantitative pipelines.

## 1. Overview

The manifest system replaces static environment variables and scattered `.env` files with a single, schema-validated JSON configuration. It allows for defining multiple **Profiles** (e.g., `production`, `repro_dev`, `crypto_heavy`) that group all parameters required for a full lifecycle run.

## 2. Manifest Schema

The manifest adheres to `configs/manifest.schema.json`. Key sections include:

- **`discovery`**: (New) Centralized universe selector configurations, replacing scattered YAML files with profile-specific filters and indicator thresholds.
- **`data`**: Parameters for data discovery, batching, and historical lookback.
- **`selection`**: Natural selection and pruning thresholds (Top N per cluster).
- **`risk`**: Hierarchical risk constraints (e.g., global cluster weight caps).
- **`backtest`**: Walk-forward validation windows (Train/Test/Step).
- **`tournament`**: Multi-engine benchmarking settings (Engines and Profiles to compare).
- **`discovery`**: (New) Centralized universe selector configurations, defining which markets to scan and which indicator thresholds to apply (e.g., ADX > 25).
- **`env`**: Environment variable overrides (e.g., GIST_ID, META_REFRESH).

## 3. Profile Selection Logic

The system follows a strict hierarchy for resolving configuration values:

1.  **Direct Environment Variables**: (Highest Priority) Variables like `TV_CLUSTER_CAP` or `TV_LOOKBACK_DAYS`.
2.  **Selected Profile**: Values defined in the active profile within `configs/manifest.json`.
3.  **Default Profile**: Values from the `production` profile (if no profile is specified).
4.  **Makefile Defaults**: Hardcoded fallbacks in the build system.

## 4. Usage

### CLI Selection
The active profile can be controlled via the `PROFILE` variable in `make`:

```bash
# Run with the institutional production profile (Default)
make daily-run

# Run with the lightweight development profile
make daily-run PROFILE=repro_dev
```

### Custom Manifests
To use an entirely different manifest file:

```bash
make daily-run MANIFEST=configs/research_experiment_v1.json PROFILE=aggressive
```

## 5. Implementation Details

- **Discovery Bridge**: Universe selectors (e.g., `FuturesUniverseSelector`) support loading configurations directly from the active profile. This ensures that market-specific filters (e.g., ADX thresholds, volume minimums) are perfectly reproducible.
- **Pydantic Integration**: The `ManifestSettingsSource` in `tradingview_scraper/settings.py` automatically injects manifest values into the application settings.
- **Makefile Bridge**: The Makefile uses a Python helper (`python -m tradingview_scraper.settings --export-env`) to ingest JSON settings into the shell environment for legacy script support.
- **Validation**: IDEs supporting JSON Schema will automatically provide autocompletion and validation when editing `configs/manifest.json`.

## 6. Best Practices for Reproducibility

1.  **Snapshotting**: For critical research runs, create a standalone manifest file (e.g., `configs/run_20251229_config.json`) and commit it.
2.  **Fixed RUN_ID**: Specify a `TV_RUN_ID` in the manifest to ensure all artifacts land in a predictable directory.
3.  **No Manual Overrides**: Avoid passing variables like `TOP_N=5` directly to the CLI; instead, create a new profile in the manifest.
