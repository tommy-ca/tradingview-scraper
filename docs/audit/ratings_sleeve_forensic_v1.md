# Forensic Audit: Binance Spot Ratings Sleeves (v1)
**Date:** 2026-01-28  
**Scope:** `all_long/short`, `ma_long/short`  
**Root Cause Investigation:** Pipeline Sparsity & Convergence  

## 1. Executive Summary
An institutional-grade forensic audit of the Binance Spot Rating sleeves reveals **extreme winner sparsity** ($N \le 4$) across all four core strategies. This sparsity has cascaded into **risk profile convergence**, where multiple optimizers (HRP, Min-Var, Max-Sharpe) produce identical or near-identical weights due to a lack of degrees of freedom in the candidate pool.

The root cause is a **silent failure in data ingestion** combined with a **strict Freshness Gate** in the consolidation layer.

## 2. Evidence & Findings

### 2.1 Funnel Attrition Matrix
| Stage | `all_long` | `all_short` | `ma_long` | `ma_short` |
| :--- | :--- | :--- | :--- | :--- |
| **Discovery (Scanner)** | 49 | 71 | 48 | 71 |
| **Consolidation (Valid)** | 4 | 2 | 3 | 2 |
| **Selection (Winners)** | 3 | 2 | 2 | 2 |

### 2.2 Root Cause: False Success in Ingestion
Audit of `scripts/services/ingest_data.py` and `PersistentDataLoader.sync` shows that symbols are being reported as "Successfully Ingested" even when the API returns 0 new candles.
- **Example**: `BINANCE:ETHUSDT` last updated Jan 16 (12 days ago).
- **Behavior**: `ingest_data` calls `sync`. `sync` finds 0 new candles. `ingest_data` checks if the file exists (it does, from Jan 16) and reports `INFO - Successfully ingested BINANCE:ETHUSDT`.
- **Result**: The file modification time (`mtime`) is NOT updated, or remains older than the threshold.

### 2.3 Cascade: Freshness Gate Veto
`scripts/services/consolidate_candidates.py` enforces a 168h (7-day) staleness threshold.
- **Action**: Any asset not updated in the last 7 days is dropped.
- **Impact**: Major pairs (BTC, ETH, SOL) which failed to sync correctly are VETOED from the universe, leaving only a few lucky alts that happened to have fresh data.

### 2.4 Impact: Profile Convergence
Because the candidate pool is reduced to 2-4 assets, the mathematical solvers in `skfolio` and `riskfolio` converge to the same solution (often Equal Weight or a simple inverse-volatility allocation).
- **Evidence**: Audit ledger shows `PROFILE_CONVERGENCE` warnings for nearly all windows and all risk profiles.

## 3. Immediate Action Plan

### 3.1 Pipeline Hardening (Remediation)
1. **Fix Ingestion Reporter**: Update `IngestionService` to verify `added_records > 0` or a change in `mtime` before reporting success.
2. **Debug Major Pair Sync**: Investigate why TradingView `Streamer` fails to fetch recent daily OHLCV for high-traffic pairs like `BTCUSDT`.

### 3.2 Audit Policy Updates
- **Mandatory Freshness Audit**: Add a pre-production check that fails the entire Alpha run if "Anchor Assets" (BTC/ETH) are missing or stale.
- **Relaxation Protocol**: If data delay is systemic, formalize a "Research Mode" that allows older data but flags it in reports.

### 3.3 Verification (2026-01-29)
- **Execution**: Reran `flow-data` for `binance_spot_rating_all_long`, `all_short`, `ma_long`.
- **Findings**:
    - `all_long` & `ma_long`: BTC/ETH/SOL correctly excluded (Bearish Market, Ratings < 0).
    - `all_short`: BTC/ETH/SOL **Successfully Recruited** (Found in `candidates.json`).
    - **Ingestion**: Confirmed "Fresh" status for major pairs, proving they are no longer being vetoed by the Freshness Gate.
- **Conclusion**: The "Freshness Gate Veto" issue is RESOLVED. Major pairs are now correctly flowing through the pipeline when their rating matches the sleeve intent.

## 4. References
- `audit.jsonl` for run `binance_spot_rating_all_long_20260128-192250`
- `scripts/services/consolidate_candidates.py` (Freshness Gate logic)
- `scripts/services/ingest_data.py` (Ingestion reporting logic)
- `docs/specs/requirements_v3.md` (Section 6.5: Ingestion Invariants)
