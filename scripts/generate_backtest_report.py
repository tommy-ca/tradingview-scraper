import json
from typing import Any, Dict, List, Optional

import pandas as pd

from tradingview_scraper.settings import get_settings

PROFILES = ["min_variance", "risk_parity", "max_sharpe", "barbell"]
SUMMARY_COLS = [
    "Profile",
    "total_cumulative_return",
    "annualized_return",
    "annualized_vol",
    "avg_window_sharpe",
    "sortino",
    "calmar",
    "win_rate",
    "Details",
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
    """
    Generates the 'backtest_comparison.md' Strategy Resume.
    Now pulls from 'tournament_results.json' to ensure consistency.
    Defaults to the [cvxportfolio simulator] and [custom engine] as the production baseline.
    """
    summary_dir = get_settings().prepare_summaries_run_dir()
    tournament_path = summary_dir / "tournament_results.json"

    if not tournament_path.exists():
        print(f"Skipping Strategy Resume: {tournament_path} not found.")
        return

    try:
        with open(tournament_path, "r") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Failed to read {tournament_path}: {e}")
        return

    all_results = data.get("results") or {}

    summary_rows = []
    regime_rows = []

    # Baseline Comparison Setup
    sim_name = "cvxportfolio" if "cvxportfolio" in all_results else "custom"
    eng_name = "custom"

    # Add Market Baseline Row
    market_prof = all_results.get(sim_name, {}).get("market", {}).get("buy_hold")
    if market_prof and market_prof.get("summary"):
        m_row = dict(market_prof["summary"])
        m_row["Profile"] = "MARKET (SPY)"
        m_row["Details"] = f"[Metrics]({sim_name}_market_buy_hold_full_report.md)"
        summary_rows.append(m_row)

    for profile in PROFILES:
        prof_key = profile.lower()
        prof_data = all_results.get(sim_name, {}).get(eng_name, {}).get(prof_key)
        if not prof_data or not prof_data.get("summary"):
            continue

        summary = prof_data["summary"]
        row = dict(summary)
        row["Profile"] = profile.upper()
        row["Details"] = f"[Metrics]({sim_name}_{eng_name}_{prof_key}_full_report.md)"
        summary_rows.append(row)

        windows = prof_data.get("windows") or []
        for w in windows:
            regime = w.get("regime")
            ret = w.get("returns")
            if regime is not None and ret is not None:
                regime_rows.append({"Profile": profile.upper(), "Regime": regime, "Return": ret})

    if not summary_rows:
        print("No baseline results found in tournament for Strategy Resume.")
        return

    df = pd.DataFrame(summary_rows)
    for c in SUMMARY_COLS:
        if c not in df.columns:
            df[c] = None
    df = df[SUMMARY_COLS]

    header = "| " + " | ".join(SUMMARY_COLS) + " |"
    separator = "| " + " | ".join(["---"] * len(SUMMARY_COLS)) + " |"
    md_rows = []
    for _, row in df.iterrows():
        cells = []
        for c in SUMMARY_COLS:
            if c in {"Profile", "Details"}:
                cells.append(str(row[c]))
            else:
                cells.append(_fmt_num(row[c], ".4f"))
        md_rows.append("| " + " | ".join(cells) + " |")

    md_table = "\n".join([header, separator] + md_rows)

    # Regime Attribution
    if regime_rows:
        regime_df = pd.DataFrame(regime_rows)
        regime_summary = regime_df.groupby(["Regime", "Profile"])["Return"].mean().unstack()
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

    # Strategic Deployment Recommendation
    min_var_vol = _get_metric(df, "MIN_VARIANCE", "annualized_vol")
    min_var_vol_str = _fmt_num(min_var_vol, ".2%")
    max_sharpe_win_rate = _get_metric(df, "MAX_SHARPE", "win_rate")
    max_sharpe_win_rate_str = _fmt_num(max_sharpe_win_rate, ".0%")

    available_profiles = set(df["Profile"].tolist())
    preferred = [p for p in ["MAX_SHARPE", "RISK_PARITY", "MIN_VARIANCE", "BARBELL"] if p in available_profiles]
    recommendation = f"Current market conditions favor **{preferred[0]}**" if preferred else "No recommendation available."

    report = f"""# Quantitative Backtest Strategy Resume
Generated on: {pd.Timestamp.now()}
Baseline: **{eng_name}** engine on **{sim_name}** simulator.

## 1. Strategy Performance Matrix
{md_table}

## 2. Regime-Specific Attribution (Avg. Window Return)
{regime_table}

## 3. Institutional Resume
- **Simulator Fidelity**: Performance includes estimated slippage and commissions.
- **Volatility Control**: MIN_VARIANCE realized volatility: {min_var_vol_str}.
- **Alpha Capture**: MAX_SHARPE win rate: {max_sharpe_win_rate_str}.
- **Alpha Decay**: See 'engine_comparison_report.md' for detailed execution friction audit.

## 4. Strategic Deployment Recommendation
{recommendation}
"""
    out_path = summary_dir / "backtest_comparison.md"
    with open(out_path, "w") as f:
        f.write(report)
    print(f"Strategy Resume generated: {out_path}")


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or pd.isna(value):
            return None
    except Exception:
        if value is None:
            return None

    try:
        return float(value)
    except Exception:
        return None


def generate_engine_comparison_report():
    summary_dir = get_settings().prepare_summaries_run_dir()
    tournament_path = summary_dir / "tournament_results.json"
    if not tournament_path.exists():
        return

    try:
        with open(tournament_path, "r") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Failed to read {tournament_path}: {e}")
        return

    meta = data.get("meta") or {}
    all_results = data.get("results") or {}

    simulators = meta.get("simulators")
    if not isinstance(simulators, list) or not simulators:
        simulators = sorted([str(k) for k in all_results.keys()])

    profiles_meta = meta.get("profiles")
    if not isinstance(profiles_meta, list) or not profiles_meta:
        inferred = []
        for sim_blob in all_results.values():
            if not isinstance(sim_blob, dict):
                continue
            for eng_blob in sim_blob.values():
                if not isinstance(eng_blob, dict):
                    continue
                inferred.extend([k for k in eng_blob.keys() if k != "_status"])
        profiles_meta = sorted(set(inferred))

    engines_meta = meta.get("engines")
    if not isinstance(engines_meta, list) or not engines_meta:
        # Infer engines from first simulator
        if simulators:
            engines_meta = sorted([str(k) for k in all_results.get(simulators[0], {}).keys()])
        else:
            engines_meta = []

    md: List[str] = []
    md.append("# Multi-Engine Optimization Tournament Report")
    md.append(f"Generated on: {pd.Timestamp.now()}")

    if meta:
        md.append("\n## Run Parameters")
        for k in ["train_window", "test_window", "step_size", "cluster_cap"]:
            if k in meta:
                md.append(f"- **{k}**: {meta.get(k)}")
        md.append(f"- **simulators**: {', '.join([str(s) for s in (simulators or [])])}")
        md.append(f"- **profiles**: {', '.join([str(p) for p in (profiles_meta or [])])}")
        md.append(f"- **engines**: {', '.join([str(e) for e in (engines_meta or [])])}")

    cols = [
        "Engine",
        "Simulator",
        "Windows",
        "total_cumulative_return",
        "annualized_return",
        "annualized_vol",
        "avg_window_sharpe",
        "sortino",
        "calmar",
        "realized_cvar_95",
        "worst_mdd",
        "win_rate",
        "avg_turnover",
        "Details",
    ]

    fmts = {
        "total_cumulative_return": ".2%",
        "annualized_return": ".2%",
        "annualized_vol": ".2%",
        "avg_window_sharpe": ".2f",
        "sortino": ".2f",
        "calmar": ".2f",
        "realized_cvar_95": ".2%",
        "worst_mdd": ".2%",
        "win_rate": ".0%",
        "avg_turnover": ".2%",
    }

    for profile in profiles_meta or []:
        profile_key = str(profile)
        rows: List[Dict[str, Any]] = []

        for sim in simulators or []:
            sim_blob = all_results.get(sim, {})
            for eng in engines_meta or []:
                eng_blob = sim_blob.get(str(eng), {})
                if not isinstance(eng_blob, dict):
                    continue

                status = eng_blob.get("_status")
                if isinstance(status, dict) and status.get("skipped"):
                    continue

                prof_blob = eng_blob.get(profile_key)
                if not isinstance(prof_blob, dict):
                    continue

                summary = prof_blob.get("summary")
                windows = prof_blob.get("windows") or []
                if not isinstance(summary, dict) or not isinstance(windows, list) or not windows:
                    continue

                mdds: List[float] = []
                for w in windows:
                    if not isinstance(w, dict):
                        continue
                    mdd = _safe_float(w.get("max_drawdown"))
                    if mdd is not None:
                        mdds.append(mdd)
                worst_mdd = min(mdds) if mdds else None

                rows.append(
                    {
                        "Engine": str(eng),
                        "Simulator": str(sim),
                        "Windows": int(len(windows)),
                        "total_cumulative_return": summary.get("total_cumulative_return"),
                        "annualized_return": summary.get("annualized_return"),
                        "annualized_vol": summary.get("annualized_vol"),
                        "avg_window_sharpe": summary.get("avg_window_sharpe"),
                        "sortino": summary.get("sortino"),
                        "calmar": summary.get("calmar"),
                        "realized_cvar_95": summary.get("realized_cvar_95"),
                        "worst_mdd": worst_mdd,
                        "win_rate": summary.get("win_rate"),
                        "avg_turnover": summary.get("avg_turnover"),
                        "Details": f"[Metrics]({sim}_{eng}_{profile_key}_full_report.md)",
                    }
                )

        md.append(f"\n## Profile: {profile_key.upper()}")
        if not rows:
            md.append("No tournament results available.")
            continue

        # Sort by Sharpe
        rows = sorted(rows, key=lambda r: _safe_float(r.get("avg_window_sharpe")) or float("-inf"), reverse=True)

        header = "| " + " | ".join(cols) + " |"
        separator = "| " + " | ".join(["---"] * len(cols)) + " |"
        lines = [header, separator]

        for row in rows:
            cells: List[str] = []
            for c in cols:
                if c in {"Engine", "Simulator", "Windows", "Details"}:
                    cells.append(str(row.get(c, "")))
                else:
                    cells.append(_fmt_num(row.get(c), fmts.get(c, ".4f")))
            lines.append("| " + " | ".join(cells) + " |")

        md.append("\n".join(lines))

        # Alpha Decay Table
        if "custom" in (simulators or []) and "cvxportfolio" in (simulators or []):
            decay_rows = []
            for eng in engines_meta or []:
                ideal = next((r for r in rows if r["Engine"] == eng and r["Simulator"] == "custom"), None)
                real = next((r for r in rows if r["Engine"] == eng and r["Simulator"] == "cvxportfolio"), None)
                if ideal and real:
                    i_s = _safe_float(ideal.get("avg_window_sharpe"))
                    r_s = _safe_float(real.get("avg_window_sharpe"))
                    if i_s is not None and r_s is not None and i_s != 0:
                        decay = (r_s - i_s) / abs(i_s)
                        decay_rows.append({"Engine": eng, "Idealized": i_s, "Realized": r_s, "Decay": decay})

            if decay_rows:
                md.append("\n### Execution Alpha Decay (Idealized vs. High-Fidelity)")
                d_cols = ["Engine", "Idealized Sharpe", "Realized Sharpe", "Alpha Decay"]
                md.append("| " + " | ".join(d_cols) + " |")
                md.append("| " + " | ".join(["---"] * len(d_cols)) + " |")
                for dr in decay_rows:
                    md.append(f"| {dr['Engine']} | {dr['Idealized']:.2f} | {dr['Realized']:.2f} | {dr['Decay']:.1%} |")

    out_path = summary_dir / "engine_comparison_report.md"
    with open(out_path, "w") as f:
        f.write("\n".join(md) + "\n")

    print(f"Engine tournament report generated: {out_path}")


if __name__ == "__main__":
    generate_comparison_report()
    generate_engine_comparison_report()
