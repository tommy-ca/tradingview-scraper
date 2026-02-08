from typing import Any, Union

import pandas as pd


def ensure_utc_index(df_or_series: Union[pd.DataFrame, pd.Series]) -> Union[pd.DataFrame, pd.Series]:
    """
    Ensures that the index of the provided DataFrame or Series is a UTC-aware pd.DatetimeIndex.
    Supports MultiIndex by recursively localizing/converting datetime levels.
    """
    if df_or_series.index.empty:
        return df_or_series

    def _ensure_utc(idx: pd.Index) -> pd.Index:
        if isinstance(idx, pd.DatetimeIndex):
            if idx.tz is None:
                return idx.tz_localize("UTC")
            return idx.tz_convert("UTC")
        if isinstance(idx, pd.MultiIndex):
            new_levels = []
            for i, level in enumerate(idx.levels):
                if isinstance(level, pd.DatetimeIndex):
                    if level.tz is None:
                        new_levels.append(level.tz_localize("UTC"))
                    else:
                        new_levels.append(level.tz_convert("UTC"))
                else:
                    new_levels.append(level)
            return idx.set_levels(new_levels)

        # Fallback: try converting to DatetimeIndex if it's a flat index of strings/objects
        if not isinstance(idx, (pd.DatetimeIndex, pd.MultiIndex)):
            try:
                dt_idx = pd.to_datetime(idx)
                if dt_idx.tz is None:
                    return dt_idx.tz_localize("UTC")
                return dt_idx.tz_convert("UTC")
            except Exception:
                pass
        return idx

    df_or_series.index = _ensure_utc(df_or_series.index)
    return df_or_series


def normalize_to_market_day(ts: Any) -> pd.Timestamp:
    """
    Normalizes a timestamp to the standard UTC midnight (00:00:00).
    Follows Market-Day convention where late-night UTC starts (>= 21:00)
    are normalized to the NEXT business day.
    """
    ts_utc = pd.Timestamp(ts, tz="UTC")

    # Type guard for LSP
    if not isinstance(ts_utc, pd.Timestamp) or pd.isna(ts_utc):
        return ts_utc

    if ts_utc.hour >= 21:
        # Pushes late-night starts into next day
        return (ts_utc + pd.Timedelta(hours=4)).normalize()
    return ts_utc.normalize()
