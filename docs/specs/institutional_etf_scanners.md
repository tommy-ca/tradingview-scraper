# Specification: Institutional ETF Discovery Pipeline

## Overview
The Institutional ETF Discovery Pipeline provides a high-fidelity, cross-asset universe spanning Equities, Bonds, and Commodities. It is designed to emit a stable, institutional-grade basket of assets for hierarchical risk parity (HRP) and barbell allocation.

## Multi-Asset Coverage
The pipeline is composed of four specialized sub-scanners:

1.  **Broad Index ETFs** (`index_etf_trend`): Captures the core market beta across S&P 500, Nasdaq 100, Russell 2000, and Emerging Markets.
2.  **Sector Select ETFs** (`sector_etf_trend`): Provides granular exposure to the 11 SPDR Select Sectors (Technology, Financials, Healthcare, etc.).
3.  **Liquid Bond ETFs** (`bond_trend`): Includes Investment Grade (LQD), High Yield (HYG), and various Treasury durations (TLT, IEF, SHY).
4.  **Commodity ETFs** (`commodity_etf_trend`): Broad coverage including Gold (GLD/IAU), Silver (SLV), Crude Oil (USO/BNO), Natural Gas (UNG), Copper (CPER), Base Metals (DBB), and thematic commodities like Uranium (URA) and Lithium (LIT).

## Pattern Standards
- **Foundation Patterns**: All ETF scanners inherit from `configs/base/hygiene/institutional.yaml`.
- **Static Mode**: Primary universes use `static_mode: true` to ensure a deterministic discovery of institutional "anchor" assets even during API instability.
- **Trend Gating**: Strategic "Alpha" scanners typically disable trend-gating sub-rules (`adx`, `recommendation`) to ensure the full basket enters the Factor Analysis phase where regime-aware pruning occurs.
- **Liquidity Floor**: Standardized at **$10M USD min daily turnover** (Value.Traded) via the institutional hygiene layer.

## Audit Checklist (Jan 2026)
- [x] Pattern Consistency: All L4 scanners use `value_traded_min: 0` to defer pruning to the selection engine.
- [x] Namespace Integrity: Correct usage of `AMEX:` and `NASDAQ:` for US ETF listings.
- [x] Metadata Completeness: All static emitters explicitly fetch volume and value metrics.
- [x] Deterministic Discovery: Verified that static baskets are emitted even when trend gates would otherwise filter them.
- [x] Multi-Asset Balance: Unified 39-asset universe covering Equities (Index/Sector), Bonds, and Commodities.

