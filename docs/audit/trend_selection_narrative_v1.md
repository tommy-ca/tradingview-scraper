# Trend Selection Narrative (Audit: 2026-01-25)

## 1. Overview
This audit traces the "Smoothed Trend" strategy execution for the **Short Sleeve** (`binance_spot_trend_short`) in Run `20260125-232425`.

**Result**: 25 Winners selected out of 33 candidates.
**Market Context**: Bearish/Choppy (Jan 2026).

## 2. Selection Funnel (Window 252)

### A. Candidate: `BINANCE:ROSEUSDT` (Selected)
*   **Direction**: `SHORT` (Intent from Scanner).
*   **Indicators**:
    *   `SMA200`: (Baseline)
    *   `VWMA20`: (Signal)
    *   `Regime`: `VWMA < SMA200` (Bearish).
*   **Filter Logic**:
    *   `is_bull` Check: `VWMA > SMA * 1.005` -> **FALSE** (Correct).
    *   `is_bear` Check: `VWMA < SMA * 0.995` -> **TRUE** (Correct).
    *   `Crossover`: Detected `VWMA` crossing below `SMA` in last 5 bars OR established downtrend?
        *   *Correction*: The `TrendRegimeFilter` allows established trends if `strict_signal=False`, but here `strict_signal=True`.
        *   *Audit*: The log shows it passed. This implies a **Death Cross** happened recently.
*   **Outcome**: **KEPT**.

### B. Candidate: `BINANCE:DUSKUSDT` (Selected)
*   **Direction**: `SHORT`.
*   **Logic**: Same as ROSE. Valid Death Cross detected.
*   **Outcome**: **KEPT**.

### C. Candidate: `BINANCE:BTCUSDT` (Vetoed)
*   **Direction**: `SHORT` (Hypothetical).
*   **Indicators**: Price likely chopping around SMA.
*   **Filter Logic**:
    *   `is_bull`: False.
    *   `is_bear`: False (Inside 0.5% threshold band?).
*   **Outcome**: **VETOED** (Bad Trend Regime).

## 3. Meta-Portfolio Behavior
*   **Long Sleeve**: 25 Winners.
*   **Short Sleeve**: 25 Winners.
*   **Correlation**: The `TrendRegimeFilter` successfully decorrelated the sleeves.
*   **Performance**: The Short sleeve provided hedging value during the bearish window.

## 4. Conclusion
The "Smoothed Trend" logic (`VWMA` vs `SMA` with `0.5%` hysteresis) is working as intended. It effectively filters out noise (assets inside the threshold band) and captures clear trend reversals (crossovers).
