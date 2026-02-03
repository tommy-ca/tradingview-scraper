from typing import Any, Union

import pandas as pd


def ensure_utc_index(df_or_series: Union[pd.DataFrame, pd.Series]) -> Union[pd.DataFrame, pd.Series]:
    """
    Ensures that the index of the provided DataFrame or Series is a UTC-aware pd.DatetimeIndex.
    Handles:
    1. Converting to DatetimeIndex if necessary.
    2. Localizing naive indices to UTC.
    3. Converting aware indices to UTC.
    4. Normalizing "contaminated" indices by stripping existing tz info before re-applying UTC.
    """
    if df_or_series.index.empty:
        return df_or_series

    # 1. Ensure pd.DatetimeIndex
    if not isinstance(df_or_series.index, pd.DatetimeIndex):
        try:
            df_or_series.index = pd.to_datetime(df_or_series.index)
        except Exception:
            # Fallback for complex indices that to_datetime might fail on
            return df_or_series

    idx = df_or_series.index

    # 2. & 3. Localization and Conversion
    if idx.tz is None:
        # Naive index
        df_or_series.index = idx.tz_localize("UTC")
    else:
        # Aware index - convert to UTC
        df_or_series.index = idx.tz_convert("UTC")

    return df_or_series


def normalize_to_market_day(ts: Any) -> pd.Timestamp:
    """
    Normalizes a timestamp to the standard UTC midnight (00:00:00).
    Follows Market-Day convention where late-night UTC starts (>= 21:00)
    are normalized to the NEXT business day.
    """
    ts_utc = pd.Timestamp(ts, tz="UTC")
    if ts_utc.hour >= 21:
        # Pushes late-night starts into next day
        return (ts_utc + pd.Timedelta(hours=4)).normalize()
    return ts_utc.normalize()
