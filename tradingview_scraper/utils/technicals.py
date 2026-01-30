from typing import Optional, cast

import numpy as np
import pandas as pd
import pandas_ta_classic as ta


class TechnicalRatings:
    """
    Utility class to reconstruct TradingView technical ratings from OHLCV data.
    """

    @staticmethod
    def _safe_vote(cond_buy: pd.Series, cond_sell: pd.Series, index: pd.Index) -> pd.Series:
        """Helper to create a vote series with proper alignment."""
        # Align series to index (fast path if already aligned)
        b = cond_buy.reindex(index, fill_value=False).to_numpy(dtype=bool)
        s = cond_sell.reindex(index, fill_value=False).to_numpy(dtype=bool)

        # Vectorized subtraction: True(1) - False(0) = 1, False(0) - True(1) = -1
        return pd.Series(b.astype(float) - s.astype(float), index=index)

    @staticmethod
    def calculate_recommend_ma_series(df: pd.DataFrame) -> pd.Series:
        """
        Reconstructs the 'Recommend.MA' rating as a time-series.
        Components: SMA (10-200), EMA (10-200), VWMA(20), HullMA(9), Ichimoku.
        """
        if df.empty:
            return pd.Series(dtype=float)

        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df.get("volume")

        all_votes = []

        # Standard lengths: 10, 20, 30, 50, 100, 200
        lengths = [10, 20, 30, 50, 100, 200]

        for length in lengths:
            # SMA
            sma = ta.sma(close, length=length)
            if sma is not None:
                sma_s = cast(pd.Series, sma)
                all_votes.append(TechnicalRatings._safe_vote(close.gt(sma_s), close.lt(sma_s), df.index))
            # EMA
            ema = ta.ema(close, length=length)
            if ema is not None:
                ema_s = cast(pd.Series, ema)
                all_votes.append(TechnicalRatings._safe_vote(close.gt(ema_s), close.lt(ema_s), df.index))

        # 2. Hull MA (9)
        hma = ta.hma(close, length=9)
        if hma is not None:
            hma_s = cast(pd.Series, hma)
            all_votes.append(TechnicalRatings._safe_vote(close.gt(hma_s), close.lt(hma_s), df.index))

        # 3. VWMA (20)
        if volume is not None:
            vwma = ta.vwma(close, cast(pd.Series, volume), length=20)
            if vwma is not None:
                vwma_s = cast(pd.Series, vwma)
                all_votes.append(TechnicalRatings._safe_vote(close.gt(vwma_s), close.lt(vwma_s), df.index))

        # 4. Ichimoku
        ichimoku_data = ta.ichimoku(high, low, close, tenkan=9, kijun=26, senkou=52)
        if ichimoku_data is not None and isinstance(ichimoku_data, tuple):
            ichimoku_df = ichimoku_data[0]
            # TV Logic likely compares Current Price vs Current Cloud (calculated from T-26).
            span_a = cast(pd.Series, ichimoku_df["ISA_9"]).shift(26)
            span_b = cast(pd.Series, ichimoku_df["ISB_26"]).shift(26)

            mx = np.maximum(span_a, span_b)
            mn = np.minimum(span_a, span_b)

            all_votes.append(TechnicalRatings._safe_vote(close.gt(mx), close.lt(mn), df.index))

        if not all_votes:
            return pd.Series(0.0, index=df.index)

        # Concatenate and mean across indicators
        concatenated = pd.concat(all_votes, axis=1)
        res = concatenated.mean(axis=1)
        return cast(pd.Series, res)

    @staticmethod
    def calculate_recommend_ma(df: pd.DataFrame) -> float:
        series = TechnicalRatings.calculate_recommend_ma_series(df)
        return float(series.iloc[-1]) if not series.empty else 0.0

    @staticmethod
    def _safe_select(cond_buy: pd.Series, cond_sell: pd.Series, indicator: pd.Series) -> pd.Series:
        """Helper to create a vote series using np.select for performance."""
        # Align to indicator index
        b = cond_buy.reindex(indicator.index, fill_value=False).values
        s = cond_sell.reindex(indicator.index, fill_value=False).values

        # np.select is faster for multiple conditions and handles NaNs via where
        vote = np.select([b, s], [1.0, -1.0], default=0.0)
        return pd.Series(vote, index=indicator.index).where(indicator.notna(), np.nan)

    @staticmethod
    def calculate_recommend_other_series(df: pd.DataFrame) -> pd.Series:
        if df.empty:
            return pd.Series(dtype=float)

        close = df["close"]
        high = df["high"]
        low = df["low"]

        all_votes = []

        # 1. RSI
        rsi = ta.rsi(close, length=14)
        if rsi is not None:
            rsi_s = cast(pd.Series, rsi).reindex(df.index)
            all_votes.append(TechnicalRatings._safe_select(rsi_s.lt(30), rsi_s.gt(70), rsi_s))

        # 2. Stochastic
        stoch = ta.stoch(high, low, close, k=14, d=3, smooth_k=3)
        if stoch is not None:
            stoch_df = cast(pd.DataFrame, stoch).reindex(df.index)
            k = cast(pd.Series, stoch_df["STOCHk_14_3_3"])
            d = cast(pd.Series, stoch_df["STOCHd_14_3_3"])
            all_votes.append(TechnicalRatings._safe_select(k.lt(20) & k.gt(d), k.gt(80) & k.lt(d), k))

        # 3. CCI (20)
        cci = ta.cci(high, low, close, length=20)
        if cci is not None:
            cci_s = cast(pd.Series, cci).reindex(df.index)
            all_votes.append(TechnicalRatings._safe_select(cci_s.lt(-100), cci_s.gt(100), cci_s))

        # 4. ADX (14, 14)
        adx = ta.adx(high, low, close, length=14, lensig=14, scalar=True)
        if adx is not None:
            adx_df = cast(pd.DataFrame, adx).reindex(df.index)
            adx_val = cast(pd.Series, adx_df["ADX_14"])
            dmp = cast(pd.Series, adx_df["DMP_14"])
            dmn = cast(pd.Series, adx_df["DMN_14"])
            all_votes.append(TechnicalRatings._safe_select(adx_val.gt(20) & dmp.gt(dmn), adx_val.gt(20) & dmn.gt(dmp), adx_val))

        # 5. AO
        ao = ta.ao(high, low)
        if ao is not None:
            ao_s = cast(pd.Series, ao).reindex(df.index)
            all_votes.append(TechnicalRatings._safe_select(ao_s.gt(0) & ao_s.gt(ao_s.shift(1)), ao_s.lt(0) & ao_s.lt(ao_s.shift(1)), ao_s))

        # 6. Momentum
        mom = ta.mom(close, length=10)
        if mom is not None:
            mom_s = cast(pd.Series, mom).reindex(df.index)
            all_votes.append(TechnicalRatings._safe_select(mom_s.gt(0), mom_s.lt(0), mom_s))

        # 7. MACD
        macd = ta.macd(close, fast=12, slow=26, signal=9)
        if macd is not None:
            macd_df = cast(pd.DataFrame, macd).reindex(df.index)
            hist = cast(pd.Series, macd_df["MACDh_12_26_9"])
            all_votes.append(TechnicalRatings._safe_select(hist.gt(0), hist.lt(0), hist))

        # 8. Stochastic RSI
        stochrsi = ta.stochrsi(close, length=14, rsi_length=14, k=3, d=3)
        if stochrsi is not None:
            stochrsi_df = cast(pd.DataFrame, stochrsi).reindex(df.index)
            k_srsi = cast(pd.Series, stochrsi_df["STOCHRSIk_14_14_3_3"])
            all_votes.append(TechnicalRatings._safe_select(k_srsi.lt(20), k_srsi.gt(80), k_srsi))

        # 9. Williams %R
        willr = ta.willr(high, low, close, length=14)
        if willr is not None:
            willr_s = cast(pd.Series, willr).reindex(df.index)
            all_votes.append(TechnicalRatings._safe_select(willr_s.lt(-80), willr_s.gt(-20), willr_s))

        # 10. Bull Bear Power
        ema13 = ta.ema(close, length=13)
        if ema13 is not None:
            ema13_s = cast(pd.Series, ema13).reindex(df.index)
            val_s = (high.sub(ema13_s)).add(low.sub(ema13_s))
            all_votes.append(TechnicalRatings._safe_select(val_s.gt(0) & val_s.gt(val_s.shift(1)), val_s.lt(0) & val_s.lt(val_s.shift(1)), ema13_s))

        # 11. Ultimate Oscillator
        uo = ta.uo(high, low, close, fast=7, medium=14, slow=28)
        if uo is not None:
            uo_s = cast(pd.Series, uo).reindex(df.index)
            all_votes.append(TechnicalRatings._safe_select(uo_s.lt(30), uo_s.gt(70), uo_s))

        if not all_votes:
            return pd.Series(0.0, index=df.index)

        # Concatenate and mean across indicators
        concatenated = pd.concat(all_votes, axis=1)
        res = concatenated.mean(axis=1)
        return cast(pd.Series, res)

    @staticmethod
    def calculate_recommend_other(df: pd.DataFrame) -> float:
        series = TechnicalRatings.calculate_recommend_other_series(df)
        return float(series.iloc[-1]) if not series.empty else 0.0

    @staticmethod
    def calculate_recommend_all_series(df: pd.DataFrame) -> pd.Series:
        ma = TechnicalRatings.calculate_recommend_ma_series(df)
        osc = TechnicalRatings.calculate_recommend_other_series(df)
        return (ma + osc) / 2.0

    @staticmethod
    def calculate_recommend_all(df: pd.DataFrame, ma_score: Optional[float] = None, osc_score: Optional[float] = None) -> float:
        if ma_score is None:
            ma_score = TechnicalRatings.calculate_recommend_ma(df)
        if osc_score is None:
            osc_score = TechnicalRatings.calculate_recommend_other(df)
        return (ma_score + osc_score) / 2.0
