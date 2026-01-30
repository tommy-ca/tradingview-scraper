import numpy as np
import pandas as pd
import pandas_ta_classic as ta
from typing import Optional, List, Dict, Tuple, Union, cast


class TechnicalRatings:
    """
    Utility class to reconstruct TradingView technical ratings from OHLCV data.
    """

    @staticmethod
    def _safe_vote(cond_buy: pd.Series, cond_sell: pd.Series, index: pd.Index) -> pd.Series:
        """Helper to create a vote series with proper alignment."""
        v = pd.Series(0.0, index=index)
        v.loc[cond_buy.reindex(index, fill_value=False).values] = 1.0
        v.loc[cond_sell.reindex(index, fill_value=False).values] = -1.0
        return v

    @staticmethod
    def calculate_adx_series(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
        res = ta.adx(high, low, close, length=14, lensig=14)
        if res is not None and not res.empty:
            return res["ADX_14"]
        return pd.Series(dtype=float, index=close.index)

    @staticmethod
    def calculate_adx_full_series(high: pd.Series, low: pd.Series, close: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Returns ADX_14, DMP_14 (+DI), DMN_14 (-DI)"""
        res = ta.adx(high, low, close, length=14, lensig=14)
        if res is not None and not res.empty:
            return res["ADX_14"], res["DMP_14"], res["DMN_14"]
        empty = pd.Series(dtype=float, index=close.index)
        return empty, empty, empty

    @staticmethod
    def calculate_donchian_series(high: pd.Series, low: pd.Series, length: int = 20) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Returns Lower, Middle, Upper Donchian Channels"""
        res = ta.donchian(high, low, lower_length=length, upper_length=length)
        if res is not None and not res.empty:
            # pandas_ta column names: DCL_20_20, DCM_20_20, DCU_20_20
            l_col = f"DCL_{length}_{length}"
            m_col = f"DCM_{length}_{length}"
            u_col = f"DCU_{length}_{length}"
            return res[l_col], res[m_col], res[u_col]
        empty = pd.Series(dtype=float, index=high.index)
        return empty, empty, empty

    @staticmethod
    def calculate_bb_width_series(close: pd.Series, length: int = 20, std: float = 2.0) -> pd.Series:
        res = ta.bbands(close, length=length, std=std)
        if res is not None and not res.empty:
            # BBB_20_2.0 is Bandwidth = (Upper - Lower) / Middle * 100
            col = f"BBB_{length}_{std}"
            if col in res.columns:
                return res[col]
        return pd.Series(dtype=float, index=close.index)

    @staticmethod
    def calculate_rsi_series(close: pd.Series) -> pd.Series:
        res = ta.rsi(close, length=14)
        if res is not None and not res.empty:
            return res
        return pd.Series(dtype=float, index=close.index)

    @staticmethod
    def calculate_macd_series(close: pd.Series) -> Tuple[pd.Series, pd.Series]:
        macd = ta.macd(close, fast=12, slow=26, signal=9)
        if macd is not None and not macd.empty:
            macd = macd.reindex(close.index)
            return macd["MACD_12_26_9"], macd["MACDs_12_26_9"]
        return pd.Series(dtype=float, index=close.index), pd.Series(dtype=float, index=close.index)

    @staticmethod
    def calculate_mom_series(close: pd.Series) -> pd.Series:
        res = ta.mom(close, length=10)
        return res.reindex(close.index) if res is not None else pd.Series(dtype=float, index=close.index)

    @staticmethod
    def calculate_ao_series(high: pd.Series, low: pd.Series) -> pd.Series:
        res = ta.ao(high, low)
        return res.reindex(high.index) if res is not None else pd.Series(dtype=float, index=high.index)

    @staticmethod
    def calculate_stoch_series(high: pd.Series, low: pd.Series, close: pd.Series) -> Tuple[pd.Series, pd.Series]:
        stoch = ta.stoch(high, low, close, k=14, d=3, smooth_k=3)
        if stoch is not None and not stoch.empty:
            stoch = stoch.reindex(close.index)
            return stoch["STOCHk_14_3_3"], stoch["STOCHd_14_3_3"]
        return pd.Series(dtype=float, index=close.index), pd.Series(dtype=float, index=close.index)

    @staticmethod
    def calculate_cci_series(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
        res = ta.cci(high, low, close, length=20)
        return res.reindex(close.index) if res is not None else pd.Series(dtype=float, index=close.index)

    @staticmethod
    def calculate_willr_series(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
        res = ta.willr(high, low, close, length=14)
        return res.reindex(close.index) if res is not None else pd.Series(dtype=float, index=close.index)

    @staticmethod
    def calculate_uo_series(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
        res = ta.uo(high, low, close, fast=7, medium=14, slow=28)
        return res.reindex(close.index) if res is not None else pd.Series(dtype=float, index=close.index)

    @staticmethod
    def calculate_bb_power_series(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
        ema13 = ta.ema(close, length=13)
        if ema13 is not None and not ema13.empty:
            ema13 = ema13.reindex(close.index)
            return (high - ema13) + (low - ema13)
        return pd.Series(dtype=float, index=close.index)

    @staticmethod
    def calculate_ichimoku_kijun_series(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
        ichimoku_df, _ = ta.ichimoku(high, low, close, tenkan=9, kijun=26, senkou=52)
        if ichimoku_df is not None and not ichimoku_df.empty:
            return ichimoku_df["IKS_26"].reindex(close.index)
        return pd.Series(dtype=float, index=close.index)

    @staticmethod
    def calculate_recommend_ma_series(df: pd.DataFrame) -> pd.Series:
        """
        Reconstructs the 'Recommend.MA' rating as a time-series.
        Components: SMA (10-200), EMA (10-200), VWMA(20), HullMA(9), Ichimoku.
        """
        if df.empty:
            return pd.Series(dtype=float)

        close = cast(pd.Series, df["close"])
        high = cast(pd.Series, df["high"])
        low = cast(pd.Series, df["low"])
        volume = cast(pd.Series, df["volume"]) if "volume" in df.columns else None

        all_votes = []
        # SMA/EMA
        lengths = [10, 20, 30, 50, 100, 200]
        for length in lengths:
            sma = ta.sma(close, length=length)
            if sma is not None and not sma.empty:
                all_votes.append(TechnicalRatings._safe_vote(close > sma, close < sma, df.index))
            ema = ta.ema(close, length=length)
            if ema is not None and not ema.empty:
                all_votes.append(TechnicalRatings._safe_vote(close > ema, close < ema, df.index))

        # Hull MA (9)
        hma = ta.hma(close, length=9)
        if hma is not None and not hma.empty:
            all_votes.append(TechnicalRatings._safe_vote(close > hma, close < hma, df.index))

        # VWMA (20)
        if volume is not None:
            vwma = ta.vwma(close, volume, length=20)
            if vwma is not None and not vwma.empty:
                all_votes.append(TechnicalRatings._safe_vote(close > vwma, close < vwma, df.index))

        # Ichimoku Kijun
        kijun = TechnicalRatings.calculate_ichimoku_kijun_series(high, low, close)
        if not kijun.empty:
            all_votes.append(TechnicalRatings._safe_vote(close > kijun, close < kijun, df.index))

        if not all_votes:
            return pd.Series(0.0, index=df.index)

        return pd.concat(all_votes, axis=1).mean(axis=1)

    @staticmethod
    def calculate_recommend_ma(df: pd.DataFrame) -> float:
        series = TechnicalRatings.calculate_recommend_ma_series(df)
        return float(series.iloc[-1]) if not series.empty else 0.0

    @staticmethod
    def calculate_recommend_other_series(df: pd.DataFrame) -> pd.Series:
        if df.empty:
            return pd.Series(dtype=float)

        close = cast(pd.Series, df["close"])
        high = cast(pd.Series, df["high"])
        low = cast(pd.Series, df["low"])

        all_votes = []

        # 1. RSI
        rsi = TechnicalRatings.calculate_rsi_series(close)
        if not rsi.empty:
            vote = pd.Series(0.0, index=df.index)
            vote.loc[rsi.values < 30] = 1.0
            vote.loc[rsi.values > 70] = -1.0
            all_votes.append(vote.where(rsi.notna(), np.nan))

        # 2. Stochastic
        stoch_k, stoch_d = TechnicalRatings.calculate_stoch_series(high, low, close)
        if not stoch_k.empty:
            vote = pd.Series(0.0, index=df.index)
            vote.loc[(stoch_k.values < 20) & (stoch_k.values > stoch_d.values)] = 1.0
            vote.loc[(stoch_k.values > 80) & (stoch_k.values < stoch_d.values)] = -1.0
            all_votes.append(vote.where(stoch_k.notna(), np.nan))

        # 3. CCI (20)
        cci = TechnicalRatings.calculate_cci_series(high, low, close)
        if not cci.empty:
            vote = pd.Series(0.0, index=df.index)
            vote.loc[cci.values < -100] = 1.0
            vote.loc[cci.values > 100] = -1.0
            all_votes.append(vote.where(cci.notna(), np.nan))

        # 4. ADX (14, 14)
        adx = TechnicalRatings.calculate_adx_series(high, low, close)
        # Note: DI components are needed for full TV parity vote, but we only have ADX_14 in the helper
        # Refactor to get full ADX df if needed. For now, use the inline logic but safely.
        res_adx = ta.adx(high, low, close, length=14, lensig=14)
        if res_adx is not None and not res_adx.empty:
            adx_val = res_adx["ADX_14"]
            dmp = res_adx["DMP_14"]
            dmn = res_adx["DMN_14"]
            vote = pd.Series(0.0, index=df.index)
            vote.loc[(adx_val.values > 20) & (dmp.values > dmn.values)] = 1.0
            vote.loc[(adx_val.values > 20) & (dmn.values > dmp.values)] = -1.0
            all_votes.append(vote.where(adx_val.notna(), np.nan))

        # 5. AO
        ao = TechnicalRatings.calculate_ao_series(high, low)
        if not ao.empty:
            vote = pd.Series(0.0, index=df.index)
            vote.loc[(ao.values > 0) & (ao.values > ao.shift(1).values)] = 1.0
            vote.loc[(ao.values < 0) & (ao.values < ao.shift(1).values)] = -1.0
            all_votes.append(vote.where(ao.notna(), np.nan))

        # 6. Momentum
        mom = TechnicalRatings.calculate_mom_series(close)
        if not mom.empty:
            vote = pd.Series(0.0, index=df.index)
            vote.loc[mom.values > 0] = 1.0
            vote.loc[mom.values < 0] = -1.0
            all_votes.append(vote.where(mom.notna(), np.nan))

        # 7. MACD
        macd, macd_signal = TechnicalRatings.calculate_macd_series(close)
        if not macd.empty:
            hist = macd - macd_signal
            vote = pd.Series(0.0, index=df.index)
            vote.loc[hist.values > 0] = 1.0
            vote.loc[hist.values < 0] = -1.0
            all_votes.append(vote.where(macd.notna(), np.nan))

        # 8. Stochastic RSI
        stochrsi = ta.stochrsi(close, length=14, rsi_length=14, k=3, d=3)
        if stochrsi is not None and not stochrsi.empty:
            k = stochrsi["STOCHRSIk_14_14_3_3"]
            vote = pd.Series(0.0, index=df.index)
            vote.loc[k.values < 20] = 1.0
            vote.loc[k.values > 80] = -1.0
            all_votes.append(vote.where(k.notna(), np.nan))

        # 9. Williams %R
        willr = TechnicalRatings.calculate_willr_series(high, low, close)
        if not willr.empty:
            vote = pd.Series(0.0, index=df.index)
            vote.loc[willr.values < -80] = 1.0
            vote.loc[willr.values > -20] = -1.0
            all_votes.append(vote.where(willr.notna(), np.nan))

        # 10. Bull Bear Power
        bbp = TechnicalRatings.calculate_bb_power_series(high, low, close)
        if not bbp.empty:
            vote = pd.Series(0.0, index=df.index)
            vote.loc[(bbp.values > 0) & (bbp.values > bbp.shift(1).values)] = 1.0
            vote.loc[(bbp.values < 0) & (bbp.values < bbp.shift(1).values)] = -1.0
            all_votes.append(vote.where(bbp.notna(), np.nan))

        # 11. Ultimate Oscillator
        uo = TechnicalRatings.calculate_uo_series(high, low, close)
        if not uo.empty:
            vote = pd.Series(0.0, index=df.index)
            vote.loc[uo.values < 30] = 1.0
            vote.loc[uo.values > 70] = -1.0
            all_votes.append(vote.where(uo.notna(), np.nan))

        if not all_votes:
            return pd.Series(0.0, index=df.index)

        return pd.concat(all_votes, axis=1).mean(axis=1)

    @staticmethod
    def calculate_recommend_other(df: pd.DataFrame) -> float:
        series = TechnicalRatings.calculate_recommend_other_series(df)
        return float(series.iloc[-1]) if not series.empty else 0.0

    @staticmethod
    def calculate_recommend_all_series(df: pd.DataFrame) -> pd.Series:
        ma = TechnicalRatings.calculate_recommend_ma_series(df)
        osc = TechnicalRatings.calculate_recommend_other_series(df)

        # Institutional Weighted Formula (Phase 640)
        # Weights: MA=0.574, Other=0.3914
        return (0.574 * ma) + (0.3914 * osc)

    @staticmethod
    def calculate_recommend_all(df: pd.DataFrame, ma_score: Optional[float] = None, osc_score: Optional[float] = None) -> float:
        if ma_score is None:
            ma_score = TechnicalRatings.calculate_recommend_ma(df)
        if osc_score is None:
            osc_score = TechnicalRatings.calculate_recommend_other(df)

        # Institutional Weighted Formula (Phase 640)
        return (0.574 * ma_score) + (0.3914 * osc_score)
