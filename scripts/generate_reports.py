import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, cast

import pandas as pd

from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.metrics import get_full_report_markdown

# Add project root to path for scripts imports
sys.path.append(os.getcwd())

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("reporting_engine")

PROFILES = ["min_variance", "hrp", "max_sharpe", "barbell"]
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


def _fmt_num(val: Any, fmt: str) -> str:
    try:
        if val is None or pd.isna(val):
            return "N/A"
        return f"{float(val):{fmt}}"
    except Exception:
        return str(val)


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


class ReportGenerator:
    def __init__(self):
        self.settings = get_settings()
        self.summary_dir = self.settings.prepare_summaries_run_dir()
        self.tournament_path = self.summary_dir / "tournament_results.json"
        self.returns_dir = self.summary_dir / "returns"
        self.tearsheet_root = self.summary_dir / "tearsheets"
        self.tearsheet_root.mkdir(parents=True, exist_ok=True)

        self.data: Dict[str, Any] = {}
        if self.tournament_path.exists():
            with open(self.tournament_path, "r") as f:
                self.data = json.load(f)

        self.meta = self.data.get("meta", {})
        self.all_results = self.data.get("results", {})

        # 1. Load global benchmark (SPY)
        self.benchmark = self._load_spy_benchmark()

    def _load_spy_benchmark(self) -> Optional[pd.Series]:
        returns_path = Path("data/lakehouse/portfolio_returns.pkl")
        if not returns_path.exists():
            return None
        try:
            all_rets = cast(pd.DataFrame, pd.read_pickle(returns_path))
            symbol = self.settings.baseline_symbol
            if symbol in all_rets.columns:
                s = cast(pd.Series, all_rets[symbol])
                s.index = pd.to_datetime(s.index)
                idx = cast(pd.DatetimeIndex, s.index)
                if idx.tz is not None:
                    s.index = idx.tz_convert(None)
                return s
        except Exception as e:
            logger.warning(f"Could not load SPY benchmark: {e}")
        return None

    def generate_all(self):
        if not self.all_results:
            logger.error("No tournament results available for reporting.")
            return

        logger.info("Generating unified quantitative reports...")

        # 1. Generate individual strategy teardowns (MD/HTML)
        self._generate_strategy_teardowns()

        # 2. Generate Strategy Resume (backtest_comparison.md)
        self._generate_strategy_resume()

        # 3. Generate Slippage Decay Audit
        if self.settings.features.feat_decay_audit:
            self._generate_decay_audit()

        # 4. Generate Tournament Benchmark (engine_comparison_report.md)
        self._generate_tournament_benchmark()

        # 4. Generate Cluster Analysis reports
        self._generate_cluster_analysis()

        # 5. Generate Universe Selection report
        self._generate_selection_report()

        logger.info(f"Reporting complete. Artifacts in: {self.summary_dir}")

    def _generate_selection_report(self):
        """Generates the high-quality Universe Selection Report."""
        try:
            import importlib

            gen_sel = importlib.import_module("scripts.generate_selection_report")
            generate_selection_report = gen_sel.generate_selection_report

            logger.info("Generating Universe Selection Report...")
            generate_selection_report(
                audit_path="data/lakehouse/selection_audit.json",
                output_path=str(self.summary_dir / "selection_audit.md"),
            )
        except Exception as e:
            logger.error(f"Selection Report failed: {e}")

    def _generate_cluster_analysis(self):
        """Generates Hierarchical and Volatility Cluster Analysis reports."""
        try:
            import importlib

            analyze_c = importlib.import_module("scripts.analyze_clusters")
            analyze_clusters = analyze_c.analyze_clusters

            logger.info("Generating Hierarchical Cluster Analysis...")

            # Paths for selected candidates
            c_path = "data/lakehouse/portfolio_clusters.json"
            m_path = "data/lakehouse/portfolio_meta.json"
            o_path = self.summary_dir / "cluster_analysis.md"
            i_path = self.summary_dir / "portfolio_clustermap.png"
            v_path = self.summary_dir / "volatility_clustermap.png"

            if os.path.exists(c_path):
                analyze_clusters(
                    clusters_path=str(c_path),
                    meta_path=str(m_path),
                    returns_path="data/lakehouse/portfolio_returns.pkl",
                    stats_path="data/lakehouse/antifragility_stats.json",
                    output_path=str(o_path),
                    image_path=str(i_path),
                    vol_image_path=str(v_path),
                )
            else:
                logger.warning(f"Cluster file missing: {c_path}. Skipping detailed analysis.")

        except Exception as e:
            logger.error(f"Cluster Analysis failed: {e}")

    def _generate_strategy_teardowns(self):
        """Generates MD and HTML reports for each point in the tournament matrix."""
        best_engines = self._identify_tournament_winners()
        essential_reports = []

        if not self.returns_dir.exists():
            return

        for pkl_path in self.returns_dir.glob("*.pkl"):
            try:
                name = pkl_path.stem
                rets = cast(pd.Series, pd.read_pickle(pkl_path))
                if rets.empty:
                    continue

                rets.index = pd.to_datetime(rets.index)
                idx_rets = cast(pd.DatetimeIndex, rets.index)
                if idx_rets.tz is not None:
                    rets.index = idx_rets.tz_convert(None)

                # Identify engine/profile from name: {sim}_{eng}_{prof}
                parts = name.split("_")
                if len(parts) < 3:
                    continue
                sim, eng, prof = parts[0], parts[1], "_".join(parts[2:])

                # Output Markdown Full Report
                out_md = self.tearsheet_root / f"{name}_full_report.md"
                # Skip benchmark for market engine itself
                target_benchmark = self.benchmark if eng != "market" else None

                md_content = get_full_report_markdown(
                    rets,
                    benchmark=target_benchmark,
                    title=f"{eng.upper()} / {prof.upper()} ({sim.upper()})",
                    mode=self.settings.report_mode,
                )
                with open(out_md, "w") as f:
                    f.write(md_content)

                # Selection logic for Gist
                is_essential = False
                if sim == "cvxportfolio":
                    if eng in {"custom", "market"}:
                        is_essential = True
                    elif prof in best_engines and eng == best_engines[prof]["engine"]:
                        is_essential = True

                if is_essential:
                    essential_reports.append(out_md.name)

            except Exception as e:
                logger.error(f"Failed teardown for {pkl_path.name}: {e}")

        # Add core reports to essentials
        essential_reports.extend(
            [
                "backtest_comparison.md",
                "engine_comparison_report.md",
            ]
        )
        if self.settings.features.feat_decay_audit:
            essential_reports.append("slippage_decay_audit.md")

        essential_reports.extend(
            [
                "portfolio_report.md",
                "selection_audit.md",
                "data_health_selected.md",
                "manifest.json",
                "portfolio_clustermap.png",
                "volatility_clustermap.png",
                "factor_map.png",
                "cluster_analysis.md",
            ]
        )
        with open(self.summary_dir / "essential_reports.json", "w") as f:
            json.dump(essential_reports, f, indent=2)

    def _identify_tournament_winners(self) -> Dict[str, Dict[str, Any]]:
        best = {}
        # Use realized simulator to pick winners
        sim_name = "cvxportfolio" if "cvxportfolio" in self.all_results else "custom"
        sim_data = self.all_results.get(sim_name, {})

        for eng_name, eng_data in sim_data.items():
            if eng_name == "market" or (isinstance(eng_data, dict) and eng_data.get("_status", {}).get("skipped")):
                continue
            for prof_name, prof_data in eng_data.items():
                if prof_name == "_status":
                    continue
                summary = prof_data.get("summary")
                if not summary:
                    continue
                sharpe = _safe_float(summary.get("avg_window_sharpe")) or -999.0
                if prof_name not in best or sharpe > best[prof_name]["sharpe"]:
                    best[prof_name] = {"engine": eng_name, "sharpe": sharpe}
        return best

    def _generate_strategy_resume(self):
        """Strategy Performance Matrix comparing profiles using production baseline."""
        sim_name = "cvxportfolio" if "cvxportfolio" in self.all_results else "custom"
        eng_name = "custom"

        summary_rows = []
        regime_rows = []

        # 1. Add Market Baseline
        market_data = self.all_results.get(sim_name, {}).get("market", {})
        if market_data:
            first_prof = next((k for k in market_data.keys() if k != "_status"), None)
            if first_prof and market_data[first_prof].get("summary"):
                m_row = dict(market_data[first_prof]["summary"])
                m_row["Profile"] = "MARKET (SPY)"
                m_row["Details"] = f"[Metrics]({sim_name}_market_{first_prof}_full_report.md)"
                summary_rows.append(m_row)

        # 2. Add Risk Profiles
        display_names = {
            "min_variance": "MIN VARIANCE",
            "hrp": "HIERARCHICAL RISK PARITY (HRP)",
            "max_sharpe": "MAX SHARPE",
            "barbell": "ANTIFRAGILE BARBELL",
        }

        for prof_key in PROFILES:
            prof_data = self.all_results.get(sim_name, {}).get(eng_name, {}).get(prof_key)
            if not prof_data or not prof_data.get("summary"):
                continue

            summary = prof_data["summary"]
            row = dict(summary)
            disp_name = display_names.get(prof_key, prof_key.upper())
            row["Profile"] = disp_name
            row["Details"] = f"[Metrics]({sim_name}_{eng_name}_{prof_key}_full_report.md)"
            summary_rows.append(row)

            for w in prof_data.get("windows") or []:
                if w.get("regime") and w.get("returns") is not None:
                    regime_rows.append({"Profile": disp_name, "Regime": w["regime"], "Return": w["returns"]})

        if not summary_rows:
            return

        # Build Tables
        df = pd.DataFrame(summary_rows)
        for c in SUMMARY_COLS:
            if c not in df.columns:
                df[c] = None
        df = df[SUMMARY_COLS]

        md_matrix = df.to_markdown(index=False)

        # Regime Attribution
        regime_table = ""
        if regime_rows:
            r_df = pd.DataFrame(regime_rows)
            r_sum = r_df.groupby(["Regime", "Profile"])["Return"].mean().unstack()
            regime_table = cast(pd.DataFrame, r_sum.map(lambda x: _fmt_num(x, ".4%"))).to_markdown()

        # Build final report
        report = f"""# Quantitative Backtest Strategy Resume
Generated on: {pd.Timestamp.now()}
Baseline: **{eng_name}** engine on **{sim_name}** simulator.

## 1. Strategy Performance Matrix
{md_matrix}

## 2. Regime-Specific Attribution (Avg. Window Return)
{regime_table}

## 3. Institutional Resume
- **Simulator Fidelity**: Performance includes estimated slippage and commissions.
- **Alpha Decay**: See 'engine_comparison_report.md' for detailed execution friction audit.
"""
        with open(self.summary_dir / "backtest_comparison.md", "w") as f:
            f.write(report)

    def _generate_decay_audit(self):
        """Generates a report on Slippage Decay (Idealized vs High-Fidelity)."""
        md = []
        md.append("# Execution Slippage & Alpha Decay Audit")
        md.append(f"Generated on: {pd.Timestamp.now()}")
        md.append("\nThis report compares the **Idealized Returns** (Zero friction) against **High-Fidelity Simulation** (Slippage + Commission).\n")

        decay_rows = []
        sim_ideal = "custom"
        sim_real = "cvxportfolio"

        if sim_ideal not in self.all_results or sim_real not in self.all_results:
            return

        for eng_name in self.all_results[sim_ideal].keys():
            if eng_name == "_status" or eng_name == "market":
                continue
            for prof_name in self.all_results[sim_ideal][eng_name].keys():
                if prof_name == "_status":
                    continue

                ideal_sum = self.all_results[sim_ideal][eng_name][prof_name].get("summary")
                real_sum = self.all_results[sim_real][eng_name][prof_name].get("summary")

                if ideal_sum and real_sum:
                    ann_ideal = _safe_float(ideal_sum.get("annualized_return")) or 0.0
                    ann_real = _safe_float(real_sum.get("annualized_return")) or 0.0
                    sharpe_ideal = _safe_float(ideal_sum.get("avg_window_sharpe")) or 0.0
                    sharpe_real = _safe_float(real_sum.get("avg_window_sharpe")) or 0.0

                    decay_ann = ann_ideal - ann_real
                    decay_sharpe = sharpe_ideal - sharpe_real

                    decay_rows.append(
                        {
                            "Engine": eng_name,
                            "Profile": prof_name,
                            "Ann. Return (Ideal)": f"{ann_ideal:.2%}",
                            "Ann. Return (Real)": f"{ann_real:.2%}",
                            "Return Decay": f"{decay_ann:.2%}",
                            "Sharpe Decay": f"{decay_sharpe:.2f}",
                        }
                    )

        if decay_rows:
            df_decay = pd.DataFrame(decay_rows)
            md.append(df_decay.to_markdown(index=False))
            md.append("\n### Interpretation")
            md.append("- **Return Decay**: The annualized percentage lost to friction. High decay (>5%) suggests the strategy is trading too frequently or in illiquid assets.")
            md.append("- **Sharpe Decay**: The degradation in risk-adjusted stability. Significant decay suggests the alpha is fragile.")
        else:
            md.append("\nInsufficient data for decay comparison.")

        with open(self.summary_dir / "slippage_decay_audit.md", "w") as f:
            f.write("\n".join(md))

    def _generate_tournament_benchmark(self):
        """Comparative benchmark of all optimization engines."""
        simulators = self.meta.get("simulators") or sorted(self.all_results.keys())
        profiles = self.meta.get("profiles") or PROFILES

        md = []
        md.append("# Multi-Engine Optimization Tournament Report")
        md.append(f"Generated on: {pd.Timestamp.now()}")

        for profile in profiles:
            profile_key = str(profile)
            rows = []
            for sim in simulators:
                sim_blob = self.all_results.get(sim, {})
                for eng in sim_blob.keys():
                    if eng == "_status":
                        continue
                    eng_data = sim_blob[eng]
                    if isinstance(eng_data, dict) and eng_data.get("_status", {}).get("skipped"):
                        continue

                    prof_data = eng_data.get(profile_key)
                    if not prof_data or not prof_data.get("summary"):
                        continue

                    summary = prof_data["summary"]
                    rows.append(
                        {
                            "Engine": eng,
                            "Simulator": sim,
                            "Sharpe": summary.get("avg_window_sharpe"),
                            "Return": summary.get("annualized_return"),
                            "Vol": summary.get("annualized_vol"),
                            "MDD": summary.get("max_drawdown"),
                            "Turnover": summary.get("avg_turnover"),
                            "Details": f"[Metrics]({sim}_{eng}_{profile_key}_full_report.md)",
                        }
                    )

            if rows:
                md.append(f"\n## Profile: {profile_key.upper()}")
                df_p = pd.DataFrame(rows).sort_values("Sharpe", ascending=False)
                md.append(df_p.to_markdown(index=False))

        with open(self.summary_dir / "engine_comparison_report.md", "w") as f:
            f.write("\n".join(md))


if __name__ == "__main__":
    generator = ReportGenerator()
    generator.generate_all()
