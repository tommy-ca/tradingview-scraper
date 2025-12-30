import json
import logging
from pathlib import Path
from typing import Optional, cast

import pandas as pd
import quantstats as qs

from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.metrics import get_full_report_markdown

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("tearsheets")


def generate_tearsheets():
    settings = get_settings()
    summary_dir = settings.prepare_summaries_run_dir()
    returns_dir = summary_dir / "returns"
    tournament_path = summary_dir / "tournament_results.json"

    if not returns_dir.exists():
        logger.warning(f"Returns directory missing: {returns_dir}")
        return

    tearsheet_root = summary_dir / "tearsheets"
    tearsheet_root.mkdir(parents=True, exist_ok=True)

    # 1. Load benchmark (SPY) for relative performance
    benchmark: Optional[pd.Series] = None
    returns_path = Path("data/lakehouse/portfolio_returns.pkl")
    if returns_path.exists():
        try:
            all_rets = cast(pd.DataFrame, pd.read_pickle(returns_path))
            if "AMEX:SPY" in all_rets.columns:
                benchmark = cast(pd.Series, all_rets["AMEX:SPY"])
                # Force naive DatetimeIndex for QuantStats compatibility
                benchmark.index = pd.to_datetime(benchmark.index)
                idx = cast(pd.DatetimeIndex, benchmark.index)
                if idx.tz is not None:
                    benchmark.index = idx.tz_convert(None)
        except Exception as e:
            logger.warning(f"Could not load SPY benchmark: {e}")

    # 2. Parse Tournament Results to identify winners
    best_engines = {}  # profile -> engine_name
    if tournament_path.exists():
        try:
            with open(tournament_path, "r") as f:
                tourney = json.load(f)

            meta = tourney.get("meta", {})
            results = tourney.get("results", {})

            # Use 'cvxportfolio' simulator results to pick winners
            realized_results = results.get("cvxportfolio", {})
            for eng_name, eng_data in realized_results.items():
                if "_status" in eng_data and eng_data["_status"].get("skipped"):
                    continue
                for prof_name, prof_data in eng_data.items():
                    if prof_name == "_status":
                        continue

                    summary = prof_data.get("summary")
                    if not summary:
                        continue

                    sharpe = summary.get("avg_window_sharpe", -999)
                    if prof_name not in best_engines or sharpe > best_engines[prof_name]["sharpe"]:
                        best_engines[prof_name] = {"engine": eng_name, "sharpe": sharpe}
        except Exception as e:
            logger.error(f"Failed to identify winners from tournament: {e}")

    essential_reports = []

    # 3. Iterate through pkl files in returns dir
    for pkl_path in returns_dir.glob("*.pkl"):
        try:
            name = pkl_path.stem
            logger.info(f"Generating tearsheet for: {name}")

            rets = cast(pd.Series, pd.read_pickle(pkl_path))
            if rets.empty:
                continue

            # Force naive DatetimeIndex
            rets.index = pd.to_datetime(rets.index)
            idx_rets = cast(pd.DatetimeIndex, rets.index)
            if idx_rets.tz is not None:
                rets.index = idx_rets.tz_convert(None)

            # Output HTML
            out_html = tearsheet_root / f"{name}.html"
            qs.reports.html(rets, benchmark=benchmark, output=str(out_html), title=f"Strategy: {name}", download_filename=f"{name}.html")

            # Output Markdown Full Report
            out_md = tearsheet_root / f"{name}_full_report.md"
            md_content = get_full_report_markdown(rets, benchmark=benchmark, title=name, mode=settings.report_mode)
            with open(out_md, "w") as f:
                f.write(md_content)

            # --- Essential Selection Logic ---
            # Criteria:
            # 1. Production Baseline: custom engine + cvxportfolio simulator
            # 2. Market Baseline: market + cvxportfolio simulator
            # 3. Tournament Winners: best engine per profile in cvxportfolio simulation

            is_essential = False
            sim, eng, prof = "", "", ""
            # name format: {simulator}_{engine}_{profile}
            parts = name.split("_")
            if len(parts) >= 3:
                sim, eng, prof = parts[0], parts[1], "_".join(parts[2:])

                # We only sync REALIZED (cvxportfolio) results to Gist to keep it clean
                if sim == "cvxportfolio" or (eng == "market" and sim == "custom"):
                    if eng == "custom" or eng == "market":
                        is_essential = True
                    elif prof in best_engines and eng == best_engines[prof]["engine"]:
                        is_essential = True

            if is_essential:
                # QuantStats report generation
                # Skip benchmark for market engine itself to avoid "Comparing to self"
                target_benchmark = benchmark if eng != "market" else None

                out_md = tearsheet_root / f"{name}_full_report.md"
                md_content = get_full_report_markdown(rets, benchmark=target_benchmark, title=name, mode=settings.report_mode)
                with open(out_md, "w") as f:
                    f.write(md_content)

                essential_reports.append(out_md.name)

        except Exception as e:
            logger.error(f"Failed to generate tearsheet for {pkl_path.name}: {e}")

    # Save manifest of essential reports
    # Include core system reports by default
    essential_reports.extend(
        [
            "data_health_selected.md",
            "data_health_raw.md",
            "backtest_comparison.md",
            "engine_comparison_report.md",
            "portfolio_report.md",
            "selection_audit.md",
            "portfolio_clustermap.png",
            "volatility_clustermap.png",
            "factor_map.png",
        ]
    )

    with open(summary_dir / "essential_reports.json", "w") as f:
        json.dump(essential_reports, f, indent=2)

    logger.info(f"Tearsheet generation complete. Root: {tearsheet_root}")


if __name__ == "__main__":
    generate_tearsheets()
