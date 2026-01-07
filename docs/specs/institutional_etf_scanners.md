# Specification: Institutional ETF Discovery Pipeline

## Overview
The Institutional ETF Discovery Pipeline provides a high-fidelity, cross-asset universe spanning Equities, Bonds, and Commodities. It is designed to emit a stable, institutional-grade basket of assets for hierarchical risk parity (HRP) and barbell allocation.

## Multi-Asset Coverage
The pipeline is composed of seven specialized sub-scanners:

### Layer A: Deterministic Anchors (Static)
1.  **Broad Index ETFs** (`index_etf_trend`): Core market beta (SPY, QQQ, IWM, VTI, etc.).
2.  **Sector Select ETFs** (`sector_etf_trend`): 11 SPDR Select Sectors (XLK, XLF, XLV, etc.).
3.  **Liquid Bond ETFs** (`bond_trend`): Institutional bond anchors (LQD, HYG, TLT, IEF, SHY).
4.  **Commodity ETF Anchors** (`commodity_etf_trend`): Canonical hard assets (GLD, SLV, USO, UNG).

### Layer B: Dynamic Aggressors (Trend-Based)
5.  **Equity Momentum** (`etf_equity_momentum`): Dynamically discovers top-performing growth/thematic ETFs (e.g., SILJ, MUU).
6.  **Bond Yield Trend** (`etf_bond_yield_trend`): Identifies emerging trends in specialized fixed income (e.g., HYLS, Senior Loans).
7.  **Commodity Supercycle** (`etf_commodity_supercycle`): Captures secular momentum in hard assets (e.g., AGQ, Platinum, Uranium).

## Pattern Standards
- **Foundation Patterns**: All ETF scanners inherit from `configs/base/hygiene/institutional.yaml`.
- **Market Categorization**: Uses numeric TradingView `category` IDs for robust filtering:
    - `["26", "27"]`: Equities
    - `["61", "70", "68", "59", "58", "63", "62", "69", "64", "56", "57"]`: Bonds
    - `["8", "6", "4", "7", "5"]`: Commodities
- **Liquidity Floor**: Standardized at **$10M USD min daily turnover** (Value.Traded).
- **Trend Quality**: Enforces `ADX > 20` and multi-horizon momentum for dynamic discovery.

## Audit Checklist (Jan 2026)
- [x] Pattern Consistency: All L4 scanners use `value_traded_min: 0` to defer pruning to the selection engine.
- [x] Namespace Integrity: Correct usage of `AMEX:` and `NASDAQ:` for US ETF listings.
- [x] Metadata Completeness: All static emitters explicitly fetch volume and value metrics.
- [x] Deterministic Discovery: Verified that static baskets are emitted even when trend gates would otherwise filter them.
- [x] Multi-Asset Balance: Unified 39-asset universe covering Equities (Index/Sector), Bonds, and Commodities.

