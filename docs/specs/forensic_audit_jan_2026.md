# Forensic Audit: Institutional ETF Outliers (Jan 2026)

## Overview
This document tracks specific asset outliers and selection vetoes identified during the Q1 2026 institutional ETF validation. These outliers serve as test cases for improving the risk engine and selection logic.

## 1. High-Fragility Outliers
These assets passed technical filters but exhibited abnormal tail-risk metrics in the factor analysis phase.

| Symbol | Fragility Score | Regime | Context |
| :--- | :--- | :--- | :--- |
| `NASDAQ:PLTR` | **1.33** | TURBULENT | High kurtosis and erratic volume spikes. Capped at **0.28%** in HRP. |
| `AMEX:CPER` | **1.47** | TURBULENT | Copper proxy exhibiting extreme negative skewness. Capped at **1.27%** in HRP. |

**Audit Findings**: The HRP (Hierarchical Risk Parity) engine successfully isolated these outliers, granting them minimal weights in defensive profiles while allowing alpha-chasing profiles (Max Sharpe) to maintain exposure.

## 2. Selection Vetoes (Operation Darwin)
These assets were discovery candidates but were vetoed by the V3 engine.

| Symbol | Veto Reason | Momentum | ECI (Friction) |
| :--- | :--- | :--- | :--- |
| `NASDAQ:TLT` | High friction relative to Momentum | -3.98% | 0.20% |
| `AMEX:USO` | High friction relative to Momentum | 2.58% | 1.65% |
| `AMEX:DBA` | High friction relative to Momentum | -2.84% | 5.04% |

**Audit Note**: The ECI (Estimated Cost of Implementation) for `AMEX:DBA` (5.04%) correctly identifies the illiquidity risk, protecting the institutional portfolio from high-churn losses.

## 4. Selection Alpha Parity Audit (Certified)
A side-by-side audit was performed using a fixed 300d lookback to resolve previous variance.

| Spec | Selected | Raw Pool EW | Filtered EW | **Selection Alpha** |
| :--- | :--- | :--- | :--- | :--- |
| **v3.2** (Champion) | 31/36 | 30.44% | 33.41% | **+2.97%** |
| **v2.1** (Anchor) | 33/36 | 28.86% | 30.61% | **+1.75%** |

**Audit Conclusion**: `v3.2` provides **+1.22%** superior selection precision over the `v2.1` anchor. The multiplicative Log-MPS engine successfully identifies high-alpha contributors while discarding lower-quality momentum signals that `v2.1` (Additive) tends to retain.

**Provenance**: 
- v3.2 Run: `20260107-043348`
- v2.1 Run: `20260107-043702`
