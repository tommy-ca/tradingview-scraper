# Specification: Workflow Configuration Manifests

This document defines the architecture and usage of the JSON-based workflow manifest system, designed to ensure institutional reproducibility and type-safety for multi-asset quantitative pipelines.

## 1. Overview

The manifest system replaces static environment variables and scattered `.env` files with a single, schema-validated JSON configuration. It allows for defining multiple **Profiles** (e.g., `production`, `repro_dev`, `crypto_heavy`) that group all parameters required for a full lifecycle run.

## 2. Profile Aliasing and Hierarchy

To maintain institutional stability while allowing for experimental iterations, the manifest supports a hierarchical profile structure, string-based aliasing, and global defaults.

### 2.1 Standardized Profiles
| Profile Name | Role | Description |
| :--- | :--- | :--- |
| **`production`** | **Alias** | Points to the currently validated institutional snapshot (e.g., `production_2026_q1`). |
| **`canary`** | **Snapshot** | Experimental environment for testing new quantitative features (e.g., Spectral Regimes). |
| **`development`** | **Snapshot** | Optimized for speed and rapid iteration (Short lookback, small universe). |
| **`production_YYYY_QX`** | **Snapshot** | Immutable historical snapshots of audited production settings. |

### 2.2 Global Defaults (`defaults`)
The manifest includes a top-level `defaults` block containing parameters shared by all profiles. Profiles only need to define the "delta" from these defaults.

### 2.3 The 5-Layer Resolution Order
1.  **CLI Flags**: Highest priority tactical overrides.
2.  **Environment Variables**: OS-level `TV_` prefixed variables.
3.  **Active Profile**: Profile-specific overrides.
4.  **Manifest Defaults**: Global baseline.
5.  **Code Defaults**: Safety fallbacks.

## 3. Manifest Schema

The manifest adheres to `configs/manifest.schema.json`. Key sections include:

- **`defaults`**: The secular institutional baseline for all settings.
- **`integrations`**: External service IDs (e.g., Gist IDs).
- **`execution_env`**: Lists mandatory environment variables and secrets.
- **`discovery`**: Composable discovery pipelines using L0-L4 hierarchy.
- **`data`**: Parameters for data discovery, batching, historical lookback, and health gates.
- **`selection`**: Natural selection and pruning thresholds (Top N per cluster).
- **`risk`**: Hierarchical risk constraints (e.g., global cluster weight caps).
- **`backtest`**: Walk-forward validation windows (Train/Test/Step) and simulator settings.
- **`features`**: Gradual rollout feature gates for 2026 Quantitative roadmap features.


## 4. Usage

### CLI Selection
The active profile can be controlled via the `PROFILE` variable in `make`:

```bash
# Run with the institutional production profile (Default)
make flow-production

# Run with the lightweight development profile
make flow-production PROFILE=development
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

## 6. Institutional Reproducibility Features

### 6.1 Manifest Archiving
Every run automatically snapshots the active `manifest.json` into its run-scoped directory (`artifacts/summaries/runs/<RUN_ID>/manifest.json`). This ensures that every implemented portfolio is accompanied by its full historical configuration context.

### 6.2 Target Row Enforcement
The system uses `PORTFOLIO_MIN_DAYS_FLOOR` to ensure that only assets with sufficient history (e.g., 320 days for a 500-day lookback) are allowed into the implementation universe, guaranteeing the integrity of long-duration backtests.

### 6.3 Hard Health Gates
In `production` mode (`strict_health: true`), the pipeline will fail-fast if any selected symbols have unresolved data gaps after the automated recovery phase, preventing capital allocation on degraded data.
