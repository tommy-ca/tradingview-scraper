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
        self.all_simulation_rows: List[Dict[str, Any]] = []
        self.all_selection_data: Dict[str, Dict[int, Dict[str, Any]]] = {}  # run_id -> win_idx -> data

    def find_runs(self) -> List[Path]:
        runs_dir = Path("artifacts/summaries/runs")
        if not runs_dir.exists():
            logger.error("Runs directory not found.")
            return []

        # Support both specific ID and wildcard
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
                    return float(val)
                except (ValueError, TypeError):
                    continue
        return default

    def process_run(self, run_path: Path):
        audit_file = run_path / "audit.jsonl"
        if not audit_file.exists():
            return

        run_id = run_path.name
        self.all_selection_data[run_id] = {}

        with open(audit_file, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    ctx = entry.get("context", {})
                    win_idx = ctx.get("window_index")

                    # 1. Capture Selection (Window-wide)
                    if entry.get("step") == "backtest_select" and entry.get("status") == "success":
                        self.all_selection_data[run_id][win_idx] = {
                            "winners": entry.get("data", {}).get("winners_meta", []),
                            "audit": entry.get("data", {}).get("pipeline_audit", []),
                            "engine": ctx.get("engine", "unknown"),
                        }

                    # 2. Capture Simulation Results
                    if entry.get("step") == "backtest_simulate" and entry.get("status") == "success":
                        met = entry.get("outcome", {}).get("metrics", {})

                        # Institutional Key Aliasing Protocol (Standard v3.5.7)
                        sharpe = self._get_metric(met, ["sharpe", "Sharpe", "avg_window_sharpe"])
                        ann_ret = self._get_metric(met, ["annualized_return", "AnnRet", "Return (%)", "return"])
                        max_dd = self._get_metric(met, ["max_drawdown", "MaxDD", "MaxDD (%)"])
                        vol = self._get_metric(met, ["annualized_vol", "realized_vol", "Vol (%)", "volatility"])
                        turnover = self._get_metric(met, ["turnover", "Turnover (%)", "turnover_rate"])

                        self.all_simulation_rows.append(
                            {
                                "RunID": run_id,
                                "Window": win_idx,
                                "Selection": run_id.split("_")[-1] if "_" in run_id else "unknown",
                                "Engine": ctx.get("engine"),
                                "Profile": ctx.get("profile"),
                                "Simulator": ctx.get("simulator"),
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
        df = pd.DataFrame(self.all_simulation_rows)
        if df.empty:
            print("# ❌ No Institutional Audit Data Found")
            return

        # Institutional Metric Calculations
        def stability_score(x):
            m = float(x.mean())
            s = float(x.std())
            return m / (s + 1e-9) if not pd.isna(s) and s > 0 else 0.0

        print("\n# 🏛️ INSTITUTIONAL STABLE PERFORMANCE MATRIX (v3.5.7)")
        print(f"**Generated**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("> Note: Only successful simulation windows with non-zero metrics are included in statistical averages.")

        # Filter out "junk" data points where return or sharpe is exactly 0.0 (indicates logging failure)
        # We define validity as having at least one non-zero core risk metric
        valid_df = df[(df["Sharpe"] != 0.0) | (df["AnnRet"] != 0.0) | (df["MaxDD"] != 0.0)].copy()

        if valid_df.empty:
            logger.warning("No valid (non-zero) performance data points found. Using full dataset.")
            valid_df = df

        # Group by Selection x Profile x Engine x Simulator to ensure distinct backends aren't merged
        matrix = valid_df.groupby(["Selection", "Profile", "Engine", "Simulator"]).agg(
            {"Sharpe": ["mean", stability_score, "count"], "AnnRet": "mean", "MaxDD": ["mean", "min"], "Vol": "mean", "Turnover": "mean"}
        )

        # Flatten columns
        matrix.columns = ["Sharpe (μ)", "Stability (μ/σ)", "Windows", "AnnRet (μ)", "MaxDD (μ)", "MaxDD (tail)", "Vol (μ)", "Turnover (μ)"]
        matrix = matrix.reset_index()

        # Add Volatility Accuracy
        def vol_acc(row):
            target = VOL_BENCHMARKS.get(str(row["Profile"]), 0.50)
            realized = float(row["Vol (μ)"])
            if realized <= 0:
                return 0.0
            return 1.0 - min(1.0, abs(realized - target) / target)

        matrix["Vol Accuracy"] = matrix.apply(vol_acc, axis=1)
        matrix["Conviction"] = matrix["Sharpe (μ)"] * matrix["Stability (μ/σ)"]
        matrix = matrix.sort_values(by="Conviction", ascending=False)

        # Formatting
        display_df = matrix.copy()
        display_df["AnnRet (μ)"] = display_df["AnnRet (μ)"].apply(lambda x: f"{x:.1%}")
        display_df["MaxDD (μ)"] = display_df["MaxDD (μ)"].apply(lambda x: f"{x:.1%}")
        display_df["MaxDD (tail)"] = display_df["MaxDD (tail)"].apply(lambda x: f"{x:.1%}")
        display_df["Vol Accuracy"] = display_df["Vol Accuracy"].apply(lambda x: f"{x:.1%}")

        print(display_df.drop(columns=["Conviction"]).to_markdown(index=False))

        print("\n## 📊 Institutional Risk Profile Volatility Standards")
        print("Each profile is calibrated to a specific volatility band to ensure behavioral consistency.")
        print("| Profile | Target Vol | Behavioral Rationale |")
        print("| :--- | :--- | :--- |")
        print("| **MinVar / MarketNeutral** | **0.35** | Minimizes absolute variance; prioritizes capital preservation. |")
        print("| **HRP / Risk Parity** | **0.45 - 0.50** | Equalizes risk across clusters; resilient to idiosyncratic shocks. |")
        print("| **Equal Weight** | **0.60** | Naive exposure; captures broad system beta. |")
        print("| **Max Sharpe** | **0.90** | Aggressive alpha pursuit; accepts higher concentration and tail risk. |")

        print("\n## 🔍 Anomaly Detection & Outlier Audit")

        # 1. Crash Windows (Window MaxDD < -30%)
        crashes = df[df["MaxDD"] < -0.30]
        if not crashes.empty:
            print(f"### 🚨 Crash Events Detected ({len(crashes)})")
            # Use cast to DataFrame to help type checker if needed, but 'by' is the standard way
            print(pd.DataFrame(crashes)[["RunID", "Window", "Profile", "MaxDD"]].sort_values(by="MaxDD", ascending=True).head(20).to_markdown(index=False))

        # 2. Sharpe Outliers (Unstable Highs)
        unstable = df[df["Sharpe"] > 10.0]
        if not unstable.empty:
            print(f"### ⚠️ Sharpe Outliers Detected ({len(unstable)})")
            print(pd.DataFrame(unstable)[["RunID", "Window", "Profile", "Sharpe"]].sort_values(by="Sharpe", ascending=False).to_markdown(index=False))

        print("\n## 📈 Volatility Compliance Trace")
        vol_summary = matrix.groupby("Profile")["Vol (μ)"].mean()
        for prof_obj, realized_val in vol_summary.items():
            prof = str(prof_obj)
            realized = float(realized_val)
            target = VOL_BENCHMARKS.get(prof, 0.50)
            if realized <= 0:
                print(f"- **{prof}**: No valid Vol data found.")
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
    parser.add_argument("--run-id", default="*", help="Run ID or pattern (default: *)")
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
