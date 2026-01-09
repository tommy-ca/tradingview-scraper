import cProfile
import io
import logging
import pstats

from scripts.backtest_engine import BacktestEngine
from tradingview_scraper.settings import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("profile_backtest")


def profile_tournament():
    settings = get_settings()
    # Use raw returns for profiling to ensure we have enough data
    raw_returns_path = "data/lakehouse/portfolio_returns_raw.pkl"
    engine = BacktestEngine(returns_path=raw_returns_path)

    # Restrict to a few profiles and engines to keep profile readable
    profiles = ["hrp"]
    engines = ["custom"]
    simulators = ["custom"]

    pr = cProfile.Profile()
    pr.enable()

    logger.info("Running profiled tournament...")
    # Very few windows to ensure we get the report
    engine.run_tournament(
        profiles=profiles,
        engines=engines,
        simulators=simulators,
        train_window=200,
        test_window=20,
        step_size=200,
    )

    pr.disable()
    s = io.StringIO()
    sortby = "cumulative"
    ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
    ps.print_stats(30)  # Top 30 functions

    print(s.getvalue())

    # Also sort by internal time to find "heavy" leaf functions
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats("time")
    ps.print_stats(30)
    print("\n--- SORTED BY INTERNAL TIME ---")
    print(s.getvalue())


if __name__ == "__main__":
    profile_tournament()
