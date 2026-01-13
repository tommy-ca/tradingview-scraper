import argparse
import datetime
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("institutional_audit")

# Institutional Volatility Benchmarks (Standard v3.5.7)
VOL_BENCHMARKS = {
    "min_variance": 0.35,
    "market_neutral": 0.35,
    "hrp": 0.45,
    "risk_parity": 0.50,
    "erc": 0.50,
    "barbell": 0.50,
    "equal_weight": 0.60,
    "max_sharpe": 0.90,
}


class InstitutionalAuditor:
    """
    Definitive Audit Tool for Global Tournament Benchmarking.
    Provides stable, non-truncated matrix analysis and deep forensic traces.
    """

    def __init__(self, run_id_pattern: str = "*", output_prefix: str = "institutional_audit"):
        self.run_id_pattern = run_id_pattern
        self.output_prefix = output_prefix
        self.rows: List[Dict[str, Any]] = []

    def find_runs(self) -> List[Path]:
        runs_dir = Path("artifacts/summaries/runs")
        if not runs_dir.exists():
            logger.error("Runs directory not found.")
            return []
        if "*" in self.run_id_pattern:
            return sorted(list(runs_dir.glob(self.run_id_pattern)))
        else:
            specific = runs_dir / self.run_id_pattern
            return [specific] if specific.exists() else []

    def _get_metric(self, metrics: Dict[str, Any], keys: List[str], default: float = 0.0) -> float:
        """Robustly extracts a metric from a dict using multiple possible aliases."""
        for k in keys:
            val = metrics.get(k)
            if val is not None:
                try:
                    # Handle both float and strings like "15.5%"
                    if isinstance(val, str) and "%" in val:
                        return float(val.replace("%", "")) / 100.0
                    return float(val)
                except (ValueError, TypeError):
                    continue
        return default

    def process_run(self, run_path: Path):
        audit_file = run_path / "audit.jsonl"
        if not audit_file.exists():
            return

        run_id = run_path.name
        run_selection_mode = "unknown"

        # Pass 1: Genesis & Config (Run-level metadata)
        with open(audit_file, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if entry.get("type") == "genesis":
                        config = entry.get("config", {})
                        run_selection_mode = str(config.get("selection_mode", run_selection_mode))
                        break
                except Exception:
                    continue

        # Directory name fallback for selection mode
        if run_selection_mode == "unknown" and "_" in run_id:
            run_selection_mode = run_id.split("_")[-1]

        # Pass 2: Results (Per-window metrics)
        with open(audit_file, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if entry.get("step") == "backtest_simulate" and entry.get("status") == "success":
                        ctx = entry.get("context", {})
                        met = entry.get("outcome", {}).get("metrics", {})

                        # 1. Identify Context
                        # Use context if available, otherwise look for short-keys in metrics
                        engine = str(ctx.get("engine") or met.get("eng") or "unknown")
                        profile = str(ctx.get("profile") or met.get("prof") or "unknown")
                        simulator = str(ctx.get("simulator") or met.get("sim") or "unknown")
                        win_idx = int(ctx.get("window_index", 0))

                        # Selection mode detection: Context -> Genesis -> RunID
                        selection_mode = str(ctx.get("selection_mode") or run_selection_mode)

                        # 2. Extract Metrics using robust aliasing
                        sharpe = self._get_metric(met, ["sharpe", "Sharpe", "avg_window_sharpe", "sharpe_ratio"])
                        ann_ret = self._get_metric(met, ["annualized_return", "AnnRet", "Return (%)", "return", "total_return"])
                        max_dd = self._get_metric(met, ["max_drawdown", "MaxDD", "MaxDD (%)", "drawdown"])
                        vol = self._get_metric(met, ["annualized_vol", "realized_vol", "Vol (%)", "volatility", "annualized_volatility"])
                        turnover = self._get_metric(met, ["turnover", "Turnover (%)", "turnover_rate"])

                        self.rows.append(
                            {
                                "RunID": run_id,
                                "Selection": selection_mode,
                                "Engine": engine,
                                "Profile": profile,
                                "Simulator": simulator,
                                "Window": win_idx,
                                "Sharpe": sharpe,
                                "AnnRet": ann_ret,
                                "MaxDD": max_dd,
                                "Vol": vol,
                                "Turnover": turnover,
                            }
                        )
                except Exception:
                    continue

    def generate_report(self):
        if not self.rows:
            print("# ❌ No Institutional Audit Data Found")
            return

        df = pd.DataFrame(self.rows)

        # Data Hygiene: Filter out windows with effectively no results
        # We only keep rows where Sharpe is non-zero OR return is non-zero
        # (Actually keeping all rows to show the full matrix, even failed ones)

        def stability_score(x):
            """Institutional Stability: Mean / StdDev. Measures reliability of the alpha."""
            m = float(x.mean())
            s = float(x.std())
            if s <= 1e-9:
                return 1.0 if abs(m) > 0 else 0.0
            return m / s

        print("\n# 🏛️ INSTITUTIONAL STABLE PERFORMANCE MATRIX (v3.5.7)")
        print(f"**Generated**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"**Scope**: Scanned {len(df['RunID'].unique())} runs | Total {len(df)} successful simulation windows.")
        print("> Note: All metrics are averages across rebalance windows.")

        # Aggregation
        # We group by Simulator as well to avoid merging heterogeneous simulation methods
        group_cols = ["Selection", "Profile", "Engine", "Simulator"]
        matrix = df.groupby(group_cols).agg(
            {
                "Sharpe": ["mean", stability_score, "count"],
                "AnnRet": "mean",
                "MaxDD": ["mean", "min"],
                "Vol": "mean",
                "Turnover": "mean",
            }
        )

        # Flatten multi-index columns
        matrix.columns = ["Sharpe (μ)", "Stability (μ/σ)", "Windows", "AnnRet (μ)", "MaxDD (μ)", "MaxDD (tail)", "Vol (μ)", "Turnover (μ)"]
        matrix = matrix.reset_index()

        # Volatility Accuracy (Closeness to target risk bands)
        def vol_acc(row):
            target = VOL_BENCHMARKS.get(str(row["Profile"]), 0.50)
            realized = float(row["Vol (μ)"])
            if realized <= 0:
                return 0.0
            return 1.0 - min(1.0, abs(realized - target) / (target + 1e-9))

        matrix["Vol Accuracy"] = matrix.apply(vol_acc, axis=1)

        # Institutional Conviction: High Sharpe * High Stability
        matrix["Conviction"] = matrix["Sharpe (μ)"] * matrix["Stability (μ/σ)"]

        # Sort by Selection then Conviction
        matrix = matrix.sort_values(by=["Selection", "Conviction"], ascending=[True, False])

        # Formatting for display
        display_df = matrix.copy()

        def fmt_percent(x):
            return f"{x:.1%}" if not pd.isna(x) else "0.0%"

        def fmt_float(x):
            return f"{x:.3f}" if not pd.isna(x) else "0.000"

        display_df["AnnRet (μ)"] = display_df["AnnRet (μ)"].apply(fmt_percent)
        display_df["MaxDD (μ)"] = display_df["MaxDD (μ)"].apply(fmt_percent)
        display_df["MaxDD (tail)"] = display_df["MaxDD (tail)"].apply(fmt_percent)
        display_df["Vol Accuracy"] = display_df["Vol Accuracy"].apply(fmt_percent)
        display_df["Sharpe (μ)"] = display_df["Sharpe (μ)"].apply(fmt_float)
        display_df["Stability (μ/σ)"] = display_df["Stability (μ/σ)"].apply(lambda x: f"{x:.2f}")
        display_df["Vol (μ)"] = display_df["Vol (μ)"].apply(lambda x: f"{x:.2f}")
        display_df["Turnover (μ)"] = display_df["Turnover (μ)"].apply(lambda x: f"{x:.2f}")

        pd.set_option("display.max_rows", None)
        print(display_df.drop(columns=["Conviction"]).to_markdown(index=False))

        # 🔍 Window Forensic & Anomaly Audit
        print("\n## 🔍 Anomaly Detection & Outlier Audit")

        # 1. Crash Detection
        crashes = df[df["MaxDD"] < -0.30]
        if not crashes.empty:
            print(f"### 🚨 Crash Events Detected ({len(crashes)})")
            # Force cast or wrap to satisfy type checker
            c_df = pd.DataFrame(crashes)
            c_sorted = c_df[["RunID", "Window", "Profile", "MaxDD"]].sort_values(by="MaxDD", ascending=True)
            print(c_sorted.head(15).to_markdown(index=False))

        # 2. Extreme Sharpe Outliers (Potential math divergence)
        unstable = df[df["Sharpe"].abs() > 10.0]
        if not unstable.empty:
            print("### ⚠️ Unstable Sharpe Outliers (|Sharpe| > 10)")
            u_df = pd.DataFrame(unstable)
            u_sorted = u_df[["RunID", "Window", "Profile", "Sharpe"]].sort_values(by="Sharpe", ascending=False)
            print(u_sorted.to_markdown(index=False))

        # 📈 Volatility Band Compliance
        print("\n## 📈 Volatility Compliance Trace")
        vol_summary = matrix.groupby("Profile")["Vol (μ)"].mean()
        for prof_obj, realized_val in vol_summary.items():
            prof = str(prof_obj)
            realized = float(realized_val)
            target = VOL_BENCHMARKS.get(prof, 0.50)
            if realized <= 0:
                print(f"- **{prof}**: No valid realized volatility found.")
                continue
            status = "✅" if abs(realized - target) < 0.20 else "⚠️ DRIFT"
            print(f"- **{prof}**: Target {target:.2f} | Realized {realized:.2f} | {status}")

        # Final Export
        export_dir = Path("artifacts/reports")
        export_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = export_dir / f"{self.output_prefix}_{ts}.csv"
        df.to_csv(path, index=False)
        logger.info(f"\n[SUCCESS] Institutional Audit saved to {path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="*", help="Run ID pattern (e.g. 'full_sys_*')")
    parser.add_argument("--prefix", default="institutional_audit", help="Output filename prefix")
    args = parser.parse_args()

    auditor = InstitutionalAuditor(run_id_pattern=args.run_id, output_prefix=args.prefix)
    runs = auditor.find_runs()
    logger.info(f"Found {len(runs)} tournament runs for audit.")

    for r in runs:
        auditor.process_run(r)

    auditor.generate_report()


if __name__ == "__main__":
    main()
