import argparse
import json
import logging
import os
import sys
from typing import List, Optional

from scripts.backtest_engine import BacktestEngine, persist_tournament_artifacts
from tradingview_scraper.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("grand_4d_tournament")


class _TeeTextIO:
    def __init__(self, *streams):
        self._streams = [s for s in streams if s is not None]
        self.encoding = "utf-8"

    def write(self, data):
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="replace")
        for s in self._streams:
            try:
                s.write(data)
            except Exception:
                pass
        return len(data)

    def flush(self):
        for s in self._streams:
            try:
                s.flush()
            except Exception:
                pass


def _parse_csv(val: Optional[str]) -> Optional[List[str]]:
    if not val:
        return None
    items = [s.strip() for s in val.split(",") if s.strip()]
    return items or None


def run_grand_tournament(
    *,
    selection_modes: Optional[List[str]] = None,
    rebalance_modes: Optional[List[str]] = None,
    engines: Optional[List[str]] = None,
    profiles: Optional[List[str]] = None,
    simulators: Optional[List[str]] = None,
    train_window: Optional[int] = None,
    test_window: Optional[int] = None,
    step_size: Optional[int] = None,
    cluster_cap: Optional[float] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> None:
    settings = get_settings()

    # 1. Dimensions
    selection_modes = selection_modes or ["v2.1", "v3.1", "v3.2"]
    rebalance_modes = rebalance_modes or ["window", "daily", "daily_5pct"]

    # Tournament Standard Scope
    engines = engines or ["custom", "skfolio", "riskfolio", "pyportfolioopt", "cvxportfolio"]
    profiles = profiles or ["market", "benchmark", "equal_weight", "min_variance", "hrp", "max_sharpe", "barbell"]
    simulators = simulators or ["custom", "cvxportfolio", "vectorbt", "nautilus"]

    # Backtest Config (Production standards)
    # Prefer manifest/settings defaults unless explicitly overridden.
    train_window = int(train_window) if train_window is not None else int(settings.train_window)
    test_window = int(test_window) if test_window is not None else int(settings.test_window)
    step_size = int(step_size) if step_size is not None else int(settings.step_size)

    # Store results in a nested structure
    # Results[reb_mode][sel_mode] -> backtest_engine result
    all_results: dict = {}

    # Save original settings
    orig_reb = settings.features.feat_rebalance_mode
    orig_sel = settings.features.selection_mode
    orig_dynamic = settings.dynamic_universe

    # Enable dynamic universe for selection mode sweep
    settings.dynamic_universe = True

    try:
        run_dir = settings.prepare_summaries_run_dir()
        log_path = settings.run_logs_dir / "grand_4d_tournament.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        original_stdout = sys.stdout
        original_stderr = sys.stderr

        with open(log_path, "a", encoding="utf-8", buffering=1) as log_f:
            try:
                log_f.write(f"\n--- grand_4d_tournament start (run_id={settings.run_id}) ---\n")
            except Exception:
                pass
            root_logger = logging.getLogger()
            file_handler = logging.StreamHandler(log_f)
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(logging.Formatter("%(message)s"))
            root_logger.addHandler(file_handler)

            sys.stdout = _TeeTextIO(original_stdout, log_f)
            sys.stderr = _TeeTextIO(original_stderr, log_f)
            try:
                for reb_mode in rebalance_modes:
                    all_results[reb_mode] = {}
                    settings.features.feat_rebalance_mode = reb_mode
                    os.environ["TV_FEATURES__FEAT_REBALANCE_MODE"] = reb_mode

                    for sel_mode in selection_modes:
                        logger.info(f"\n🏆 STARTING TOURNAMENT: Rebalance={reb_mode}, Selection={sel_mode}")

                        settings.features.selection_mode = sel_mode
                        os.environ["TV_FEATURES__SELECTION_MODE"] = sel_mode

                        # Fresh engine to reload state/data if needed
                        bt = BacktestEngine()
                        cap = float(cluster_cap) if cluster_cap is not None else float(settings.cluster_cap)

                        res = bt.run_tournament(
                            train_window=train_window,
                            test_window=test_window,
                            step_size=step_size,
                            engines=engines,
                            profiles=profiles,
                            simulators=simulators,
                            cluster_cap=cap,
                            start_date=start_date,
                            end_date=end_date,
                        )

                        cell_data_dir = settings.run_data_dir / "grand_4d" / reb_mode / sel_mode
                        persist_tournament_artifacts(res, cell_data_dir)

                        all_results[reb_mode][sel_mode] = res["results"]

                        # Incremental Save
                        partial_output = {
                            "meta": {
                                "run_id": settings.run_id,
                                "dimensions": {
                                    "rebalance": rebalance_modes,
                                    "selection": selection_modes,
                                    "engines": engines,
                                    "profiles": profiles,
                                    "simulators": simulators,
                                },
                            },
                            "rebalance_audit_results": all_results,
                        }
                        with open(run_dir / "grand_4d_tournament_results_partial.json", "w") as f:
                            json.dump(partial_output, f, indent=2)

                # Final aggregation
                output = {
                    "meta": {
                        "run_id": settings.run_id,
                        "dimensions": {
                            "rebalance": rebalance_modes,
                            "selection": selection_modes,
                            "engines": engines,
                            "profiles": profiles,
                            "simulators": simulators,
                        },
                    },
                    "rebalance_audit_results": all_results,
                }

                out_path = run_dir / "grand_4d_tournament_results.json"
                with open(out_path, "w") as f:
                    json.dump(output, f, indent=2)

                settings.promote_summaries_latest()
                logger.info(f"\n✅ Grand 4D Tournament Finalized: {out_path}")
            finally:
                try:
                    root_logger.removeHandler(file_handler)
                except Exception:
                    pass
                sys.stdout = original_stdout
                sys.stderr = original_stderr

    finally:
        # Restore settings
        settings.features.feat_rebalance_mode = orig_reb
        settings.features.selection_mode = orig_sel
        settings.dynamic_universe = orig_dynamic


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection-modes", default=None, help="Comma-separated selection modes")
    parser.add_argument("--rebalance-modes", default=None, help="Comma-separated rebalance modes")
    parser.add_argument("--engines", default=None, help="Comma-separated engines")
    parser.add_argument("--profiles", default=None, help="Comma-separated profiles")
    parser.add_argument("--simulators", default=None, help="Comma-separated simulators")

    parser.add_argument("--train-window", type=int, default=None)
    parser.add_argument("--test-window", type=int, default=None)
    parser.add_argument("--step-size", type=int, default=None)
    parser.add_argument("--cluster-cap", type=float, default=None)
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)

    args = parser.parse_args()

    run_grand_tournament(
        selection_modes=_parse_csv(args.selection_modes),
        rebalance_modes=_parse_csv(args.rebalance_modes),
        engines=_parse_csv(args.engines),
        profiles=_parse_csv(args.profiles),
        simulators=_parse_csv(args.simulators),
        train_window=args.train_window,
        test_window=args.test_window,
        step_size=args.step_size,
        cluster_cap=args.cluster_cap,
        start_date=args.start_date,
        end_date=args.end_date,
    )


if __name__ == "__main__":
    main()
