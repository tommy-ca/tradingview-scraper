import json

import pandas as pd

from tradingview_scraper.settings import get_settings

PROFILES = ["min_variance", "risk_parity", "max_sharpe", "barbell"]
SUMMARY_COLS = [
    "Profile",
    "total_cumulative_return",
    "annualized_return",
    "annualized_vol",
    "avg_window_sharpe",
    "win_rate",
]


def _fmt_num(value, fmt: str) -> str:
    try:
        if value is None or pd.isna(value):
            return "N/A"
    except Exception:
        if value is None:
            return "N/A"

    try:
        return format(float(value), fmt)
    except Exception:
        return str(value)


def _get_metric(df, profile: str, metric: str):
    if df.empty or "Profile" not in df.columns or metric not in df.columns:
        return None

    sel = df.loc[df["Profile"] == profile, metric]
    if sel.empty:
        return None

    val = sel.iloc[0]
    if pd.isna(val):
        return None

    try:
        return float(val)
    except Exception:
        return None


def generate_comparison_report():
    summary_dir = get_settings().prepare_summaries_run_dir()

    summary_rows = []
    regime_rows = []

    for profile in PROFILES:
        path = summary_dir / f"backtest_{profile}.json"
        if not path.exists():
            continue

        try:
            with open(path, "r") as f:
                data = json.load(f)
        except Exception as e:
            print(f"Failed to read {path}: {e}")
            continue

        summary = data.get("summary")
        if isinstance(summary, dict):
            row = dict(summary)
            row["Profile"] = profile.upper()
            summary_rows.append(row)

        windows = data.get("windows") or []
        if isinstance(windows, list):
            for w in windows:
                if not isinstance(w, dict):
                    continue
                regime = w.get("regime")
                ret = w.get("returns")
                if regime is None or ret is None:
                    continue
                regime_rows.append({"Profile": profile.upper(), "Regime": regime, "Return": ret})

    if not summary_rows:
        print("No backtest results found.")
        return

    df = pd.DataFrame(summary_rows)

    for c in SUMMARY_COLS:
        if c not in df.columns:
            df[c] = None
    df = df[SUMMARY_COLS]

    # Manual Markdown Table Construction
    header = "| " + " | ".join(SUMMARY_COLS) + " |"
    separator = "| " + " | ".join(["---"] * len(SUMMARY_COLS)) + " |"
    rows = []
    for _, row in df.iterrows():
        cells = []
        for c in SUMMARY_COLS:
            if c == "Profile":
                cells.append(str(row[c]))
            else:
                cells.append(_fmt_num(row[c], ".4f"))
        rows.append("| " + " | ".join(cells) + " |")

    md_table = "\n".join([header, separator] + rows)

    # Goal Alignment Validation
    validation_notes = []

    min_var_vol = _get_metric(df, "MIN_VARIANCE", "annualized_vol")
    risk_parity_vol = _get_metric(df, "RISK_PARITY", "annualized_vol")
    max_sharpe_vol = _get_metric(df, "MAX_SHARPE", "annualized_vol")

    if min_var_vol is None or max_sharpe_vol is None:
        validation_notes.append("**Risk Alignment**: Insufficient data to compare MIN_VARIANCE vs MAX_SHARPE (missing one or both profiles).")
    elif min_var_vol < max_sharpe_vol:
        validation_notes.append("**Risk Alignment**: MIN_VARIANCE volatility is lower than MAX_SHARPE (target achieved).")
    else:
        validation_notes.append("**Risk Alignment**: MIN_VARIANCE volatility is not lower than MAX_SHARPE (target failed).")

    if risk_parity_vol is None or max_sharpe_vol is None or min_var_vol is None:
        validation_notes.append("**Risk Alignment**: Insufficient data to evaluate RISK_PARITY 'middle path' (missing required profiles).")
    elif risk_parity_vol < max_sharpe_vol and risk_parity_vol > min_var_vol:
        validation_notes.append("**Risk Alignment**: RISK_PARITY maintains the 'middle path' volatility (target achieved).")
    elif risk_parity_vol >= max_sharpe_vol:
        validation_notes.append("**Risk Alignment**: RISK_PARITY volatility exceeded MAX_SHARPE (diversification failure).")
    else:
        validation_notes.append("**Risk Alignment**: RISK_PARITY volatility is very low (closer to MIN_VARIANCE).")

    v_notes_str = "\n".join(f"- {n}" for n in validation_notes)

    # Regime Attribution Analysis
    if regime_rows:
        regime_df = pd.DataFrame(regime_rows)
        regime_summary = regime_df.groupby(["Regime", "Profile"])["Return"].mean().unstack()

        # Construct Regime Table
        regime_header = "| Regime | " + " | ".join([p.upper() for p in PROFILES]) + " |"
        regime_sep = "| --- | " + " | ".join(["---"] * len(PROFILES)) + " |"
        regime_lines = []
        for regime, row in regime_summary.iterrows():
            vals = []
            for p in PROFILES:
                vals.append(_fmt_num(row.get(p.upper(), None), ".4%"))
            regime_lines.append("| " + " | ".join([str(regime)] + vals) + " |")

        regime_table = "\n".join([regime_header, regime_sep] + regime_lines)
    else:
        regime_table = "No regime attribution data available."

    # Report helpers
    min_var_vol_str = _fmt_num(min_var_vol, ".2%")
    max_sharpe_win_rate = _get_metric(df, "MAX_SHARPE", "win_rate")
    max_sharpe_win_rate_str = _fmt_num(max_sharpe_win_rate, ".0%")

    available_profiles = set(df["Profile"].tolist())
    preferred = [p for p in ["MAX_SHARPE", "RISK_PARITY", "MIN_VARIANCE", "BARBELL"] if p in available_profiles]

    if len(preferred) >= 2:
        recommendation = f"Current market conditions favor **{preferred[0]}** or **{preferred[1]}** given observed stability."
    elif preferred:
        recommendation = f"Current market conditions favor **{preferred[0]}** given available backtest data."
    else:
        recommendation = "No recommendation available (no profiles found)."

    if "MIN_VARIANCE" in available_profiles:
        recommendation += " If volatility clustering increases, transition to **MIN_VARIANCE**."
    else:
        recommendation += " If volatility clustering increases, run **MIN_VARIANCE** validation and reassess."

    report = f"""# Quantitative Backtest Strategy Resume
Generated on: {pd.Timestamp.now()}

## 1. Strategy Performance Matrix
{md_table}

## 2. Regime-Specific Attribution (Avg. Window Return)
{regime_table}

## 3. Goal Alignment Validation
{v_notes_str}

## 4. Institutional Resume
- **Volatility Control**: MIN_VARIANCE realized volatility: {min_var_vol_str}.
- **Alpha Capture**: MAX_SHARPE win rate: {max_sharpe_win_rate_str}.
- **Diversification**: RISK_PARITY targets 'middle path' volatility between MIN_VARIANCE and MAX_SHARPE.
- **Tail Risk**: BARBELL is expected to exhibit higher variance and tail sensitivity.

## 5. Strategic Deployment Recommendation
{recommendation}
"""

    out_path = summary_dir / "backtest_comparison.md"
    with open(out_path, "w") as f:
        f.write(report)

    print(f"Comparison report generated: {out_path}")


if __name__ == "__main__":
    generate_comparison_report()
