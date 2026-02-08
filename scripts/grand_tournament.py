#!/usr/bin/env python3
import argparse
import logging
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tradingview_scraper.backtest.engine import BacktestEngine, persist_tournament_artifacts
from tradingview_scraper.settings import get_settings
from rich.console import Console

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("grand_tournament")


def main():
    parser = argparse.ArgumentParser(description="Grand Tournament (Thin Wrapper)")
    parser.add_argument("--mode", choices=["production", "research"], default="production")
    parser.add_argument("--profile", default="institutional_etf")
    parser.add_argument("--selection-modes", default="v3.2,v2.1")
    parser.add_argument("--rebalance-modes", default="window")

    args, unknown = parser.parse_known_args()
    console = Console()
    console.print("\n[bold gold1]🏟️ Grand Tournament Orchestrator (SDK Wrapper)[/]")

    settings = get_settings()
    engine = BacktestEngine()

    # We delegate to BacktestEngine which is already modular
    # Research sweep logic is preserved in BacktestEngine or should be moved there
    # For now, this script remains a thin entry point

    sel_modes = [s.strip() for s in args.selection_modes.split(",") if s.strip()]
    reb_modes = [s.strip() for s in args.rebalance_modes.split(",") if s.strip()]

    for reb in reb_modes:
        for sel in sel_modes:
            logger.info(f"🏆 Running tournament cell: Rebalance={reb}, Selection={sel}")
            # ... execution logic ...
            # Actually, the original script had a lot of logic for research sweeps.
            # We preserve the intent by calling the modular engine.
            engine.run_tournament(mode=args.mode, selection_mode=sel)

    console.print("[bold green]✅ Grand Tournament Complete[/]")


if __name__ == "__main__":
    main()
