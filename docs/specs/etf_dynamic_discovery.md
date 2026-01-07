# Specification: Dynamic ETF Discovery (L4)

## 1. Overview
This document defines the requirements and design for expanding the institutional ETF universe using dynamic trend and momentum-based scanners. This complements the existing static anchor discovery by identifying emerging alpha candidates that meet strict institutional liquidity and trend quality gates.

## 2. Requirements

### 2.1 Liquidity Guardrails
All dynamically discovered assets MUST meet the institutional hygiene floor to ensure executable capacity.
- **Min Daily Turnover**: $10,000,000 USD (`Value.Traded`).
- **Market Cap Floor**: $500,000,000 USD (where applicable for ETF AUM).

### 2.2 Momentum & Trend Quality
To filter out "noisy" or "choppy" assets, discovery logic utilizes multi-horizon momentum and trend strength indicators.
- **Trend Strength**: `ADX(14) > 20`.
- **Moving Average Alignment**: `EMA(20) > EMA(50)` (Bullish alignment).
- **Momentum Horizons**:
    - Short-term: `Perf.W > 0`.
    - Medium-term: `Perf.1M > 2%`.
    - Secular: `Perf.3M > 5%`.

### 2.3 Asset Class Diversity
The expansion must cover three primary macro sleeves:
1.  **Equity Aggressors**: Growth and factor-based equity ETFs.
2.  **Bond Yield Rotators**: Dynamic duration and credit-spread seekers.
3.  **Commodity Supercycle**: Hard assets and inflation proxies.

## 3. Design: The "Anchor + Aggressor" Discovery Model

The `institutional_etf` profile will utilize a composite discovery pipeline:

### Layer A: Deterministic Anchors (Static)
- **Role**: Ensures covariance matrix stability and baseline exposure.
- **Assets**: SPY, QQQ, GLD, LQD, BND, etc.
- **Mode**: `static_mode: true`.

### Layer B: Dynamic Aggressors (Trend-Based)
- **Role**: Captures emerging alpha and sector rotation.
- **Mode**: `static_mode: false` (Open-ended search).
- **Limit**: Max 50 additional symbols.

## 4. Implementation Specifications

### 4.1 Base Preset (`configs/base/universes/dynamic_etf_discovery.yaml`)
Inherits from `institutional.yaml` and enforces the $10M liquidity floor for all open-ended searches.

### 4.2 Dynamic Scanners
| Scanner ID | Logic | Target |
| :--- | :--- | :--- |
| `etf_equity_momentum` | `Perf.1M` Descending | All US Equity ETFs |
| `etf_bond_yield_trend` | `ADX > 25` + `Perf.W > 0` | All US Bond ETFs |
| `etf_commodity_supercycle`| `EMA(10) > EMA(30)` | All US Commodity ETFs |

## 5. Validation Plan
1.  **Discovery Audit**: Verify total symbol count across all 4 scanners.
2.  **Grand Tournament**: Compare "Static-Only" vs "Expanded" universes.
3.  **Alpha Isolation**: Measure the specific performance contribution of dynamically discovered assets via the `alpha_isolation.md` report.
