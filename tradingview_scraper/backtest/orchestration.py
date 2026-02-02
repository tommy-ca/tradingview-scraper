from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Generator, cast

import pandas as pd

logger = logging.getLogger("backtest.orchestration")


@dataclass(frozen=True)
class WalkForwardWindow:
    """
    Represents a single step in a walk-forward optimization.

    Attributes:
        step_index: The index where the test period starts.
        train_start: The index where the training period starts.
        train_end: The index where the training period ends (exclusive).
        test_start: The index where the test period starts.
        test_end: The index where the test period ends (exclusive).
        train_dates: Tuple of (start, end) timestamps for training.
        test_dates: Tuple of (start, end) timestamps for testing.
    """

    step_index: int
    train_start: int
    train_end: int
    test_start: int
    test_end: int
    train_dates: tuple[pd.Timestamp, pd.Timestamp]
    test_dates: tuple[pd.Timestamp, pd.Timestamp]


class WalkForwardOrchestrator:
    """
    Orchestrates time-stepping logic for Walk-Forward Analysis (WFA).

    Decouples the logic of "when to train/test" from "what to train/test".
    Supports both rolling (fixed-length) and expanding (anchored) windows.

    Industry Patterns (vectorbt, QuantConnect, OpenBB):
    - Decoupled window generation: Allows testing different windowing strategies without changing the backtest engine.
    - Support for 'Anchored' training: Important for strategies where more data is always better (Expanding Window).
    - Data-leakage prevention: Strict separation of train and test indices.
    - Recursive Aggregation: Treating strategy returns as assets for meta-portfolio optimization.
    """

    def __init__(
        self,
        train_window: int,
        test_window: int,
        step_size: int,
        anchored: bool = False,
        min_train_window: int | None = None,
    ):
        """
        Initialize the orchestrator.

        Args:
            train_window: Number of periods (bars) for training. If anchored=True,
                         this is the initial training window size.
            test_window: Number of periods (bars) for out-of-sample testing.
            step_size: Number of periods to advance the window in each step.
            anchored: If True, the training start remains at the beginning of the data
                     (expanding window). If False, the training window rolls.
            min_train_window: Minimum training size required to start.
                             Defaults to train_window.
        """
        self.train_window = train_window
        self.test_window = test_window
        self.step_size = step_size
        self.anchored = anchored
        self.min_train_window = min_train_window or train_window

    def generate_windows(self, data: pd.DataFrame | pd.Series | pd.Index) -> Generator[WalkForwardWindow, None, None]:
        """
        Generates walk-forward window definitions for the provided data.

        Yields:
            WalkForwardWindow: The indices and timestamps for the current step.
        """
        index = data.index if isinstance(data, (pd.DataFrame, pd.Series)) else data
        n_obs = len(index)

        if n_obs < self.min_train_window + self.test_window:
            logger.warning(f"Data length ({n_obs}) is insufficient for min_train ({self.min_train_window}) + test ({self.test_window})")
            return

        # Starting point: first test window starts after the initial training window
        for i in range(self.train_window, n_obs - self.test_window + 1, self.step_size):
            train_start = 0 if self.anchored else i - self.train_window
            train_end = i
            test_start = i
            test_end = min(i + self.test_window, n_obs)

            yield WalkForwardWindow(
                step_index=i,
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
                train_dates=(cast(pd.Timestamp, index[train_start]), cast(pd.Timestamp, index[train_end - 1])),
                test_dates=(cast(pd.Timestamp, index[test_start]), cast(pd.Timestamp, index[test_end - 1])),
            )

    def slice_data(self, data: pd.DataFrame, window: WalkForwardWindow) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Slices a DataFrame into train and test sets based on a window definition.
        """
        train_data = data.iloc[window.train_start : window.train_end]
        test_data = data.iloc[window.test_start : window.test_end]
        return train_data, test_data


class RecursiveMetaOrchestrator:
    """
    Advanced orchestrator for Recursive Meta-Portfolio aggregation.

    Implements the "Strategy of Strategies" pattern:
    1. Orchestrates backtests for multiple 'Sleeves'.
    2. Collects Out-of-Sample (OOS) returns from each sleeve.
    3. Aggregates OOS returns into a 'Meta-Matrix'.
    4. Runs a top-level walk-forward on the Meta-Matrix.
    """

    def __init__(self, orchestrator: WalkForwardOrchestrator):
        self.orchestrator = orchestrator
        self.sleeve_results: dict[str, pd.Series] = {}

    def aggregate_oos_returns(self, sleeve_returns: dict[str, pd.Series]) -> pd.DataFrame:
        """
        Aggregates multiple sleeve return series into a single matrix.
        Uses inner join to ensure temporal alignment for the meta-optimizer.
        """
        if not sleeve_returns:
            return pd.DataFrame()

        meta_matrix = pd.concat(sleeve_returns, axis=1)
        # Pillar 8.4: Never zero-fill weekends for crypto-TradFi correlation calculations.
        # Pillar 9.1: Mixed-direction portfolios MUST use Stable Sum Gate in rebalance simulations.
        return meta_matrix.dropna()

    def get_fractal_depth_info(self) -> dict[str, Any]:
        """Returns metadata about the recursive depth (Fractal Meta Architecture)."""
        return {
            "depth": 1,  # Placeholder for actual depth tracking
            "pattern": "Recursive Meta-Portfolio",
            "pillars_compliant": True,
        }

    def stitch_oos_returns(self, step_results: list[pd.Series]) -> pd.Series:
        """
        Stitches individual Out-of-Sample (OOS) return series into a single continuous series.
        This represents the 'Purified OOS Curve' (vectorbt pattern).
        """
        if not step_results:
            return pd.Series(dtype=float)

        full_series_raw = pd.concat(step_results)
        full_series = cast(pd.Series, full_series_raw)
        # Pillar 7.1: Ensure the returns matrix preserves real trading calendars; never zero-fill weekends.
        return full_series[~full_series.index.duplicated(keep="first")].sort_index()
