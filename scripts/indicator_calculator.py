#!/usr/bin/env python3
"""
指标计算引擎 - IndicatorCalculator

功能:
使用 TA-Lib 或纯 Python 实现计算技术指标 (ADX, MACD, RSI)
"""

import logging
from typing import Dict, Optional, Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class IndicatorCalculator:
    """
    指标计算器

    计算以下指标:
    - ADX, +DI, -DI (趋势强度)
    - MACD, Signal, Hist (动量)
    - RSI (超买超卖)
    """

    def __init__(
        self,
        adx_period: int = 14,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        rsi_period: int = 14,
    ):
        """
        初始化指标计算器

        Args:
            adx_period: ADX 计算周期
            macd_fast: MACD 快线周期
            macd_slow: MACD 慢线周期
            macd_signal: MACD 信号线周期
            rsi_period: RSI 计算周期
        """
        self.adx_period = adx_period
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.rsi_period = rsi_period

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算所有指标

        Args:
            df: 包含 OHLCV 的 DF，必须有 open, high, low, close, volume 列

        Returns:
            添加了指标列的 DF
        """
        if df.empty:
            return df

        # 确保有足够的 bars
        min_bars = max(self.adx_period, self.macd_slow, self.rsi_period) + 10
        if len(df) < min_bars:
            logger.debug(f"数据不足，需要{min_bars}条，实际{len(df)}条")
            return self._add_empty_columns(df)

        try:
            # 提取 OHLCV 数据
            highs = df["high"].values
            lows = df["low"].values
            closes = df["close"].values

            # 创建结果 DF (复制原始数据)
            result_df = df.copy()

            # 计算 ADX (使用纯 Python 实现)
            adx, plus_di, minus_di = self._calculate_adx(highs, lows, closes)
            result_df["adx"] = adx
            result_df["plus_di"] = plus_di
            result_df["minus_di"] = minus_di

            # 计算 MACD
            macd, signal, hist = self._calculate_macd(closes)
            result_df["macd"] = macd
            result_df["macd_signal"] = signal
            result_df["macd_hist"] = hist

            # 计算 RSI
            rsi = self._calculate_rsi(closes)
            result_df["rsi"] = rsi

            return result_df

        except Exception as e:
            logger.error(f"指标计算失败：{e}")
            return self._add_empty_columns(df)

    def _add_empty_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加空的指标列"""
        result_df = df.copy()
        for col in [
            "adx",
            "plus_di",
            "minus_di",
            "macd",
            "macd_signal",
            "macd_hist",
            "rsi",
        ]:
            result_df[col] = np.nan
        return result_df

    def _calculate_adx(
        self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray
    ) -> tuple:
        """
        计算 ADX 指标 (纯 Python 实现)

        Returns:
            (adx, plus_di, minus_di) 元组
        """
        # 计算 TR, +DM, -DM
        tr = np.zeros(len(closes))
        plus_dm = np.zeros(len(closes))
        minus_dm = np.zeros(len(closes))

        for i in range(1, len(closes)):
            # True Range
            tr[i] = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )

            # +DM and -DM
            up_move = highs[i] - highs[i-1]
            down_move = lows[i-1] - lows[i]

            if up_move > down_move and up_move > 0:
                plus_dm[i] = up_move
            else:
                plus_dm[i] = 0

            if down_move > up_move and down_move > 0:
                minus_dm[i] = down_move
            else:
                minus_dm[i] = 0

        # 使用 Wilder 的平滑方法计算 ATR, +DI, -DI
        atr = np.zeros(len(closes))
        plus_di = np.zeros(len(closes))
        minus_di = np.zeros(len(closes))

        # 初始值 (第一个周期的和)
        atr[self.adx_period - 1] = tr[:self.adx_period].sum() / self.adx_period
        plus_di[self.adx_period - 1] = plus_dm[:self.adx_period].sum()
        minus_di[self.adx_period - 1] = minus_dm[:self.adx_period].sum()

        # Wilder 平滑
        for i in range(self.adx_period, len(closes)):
            atr[i] = (atr[i-1] * (self.adx_period - 1) + tr[i]) / self.adx_period
            plus_di[i] = (plus_di[i-1] * (self.adx_period - 1) + plus_dm[i]) / self.adx_period
            minus_di[i] = (minus_di[i-1] * (self.adx_period - 1) + minus_dm[i]) / self.adx_period

        # 计算 +DI 和 -DI (百分比)
        for i in range(self.adx_period - 1, len(closes)):
            if atr[i] > 0:
                plus_di[i] = (plus_di[i] / atr[i]) * 100
                minus_di[i] = (minus_di[i] / atr[i]) * 100

        # 计算 DX 和 ADX
        dx = np.zeros(len(closes))
        adx = np.zeros(len(closes))

        for i in range(self.adx_period * 2 - 1, len(closes)):
            di_sum = plus_di[i] + minus_di[i]
            if di_sum > 0:
                dx[i] = abs(plus_di[i] - minus_di[i]) / di_sum * 100

        # 第一个 ADX 值是 DX 的平均
        first_dx_idx = self.adx_period * 2 - 1
        adx[first_dx_idx] = dx[first_dx_idx:self.adx_period*3-1].mean()

        # Wilder 平滑 ADX
        for i in range(first_dx_idx + 1, len(closes)):
            adx[i] = (adx[i-1] * (self.adx_period - 1) + dx[i]) / self.adx_period

        return adx, plus_di, minus_di

    def _calculate_macd(self, closes: np.ndarray) -> tuple:
        """
        计算 MACD 指标 (纯 Python 实现)

        Returns:
            (macd, signal, hist) 元组
        """
        # 计算 EMA
        def ema(data, period):
            result = np.zeros(len(data))
            multiplier = 2 / (period + 1)
            result[0] = data[0]
            for i in range(1, len(data)):
                result[i] = (data[i] - result[i-1]) * multiplier + result[i-1]
            return result

        ema_fast = ema(closes, self.macd_fast)
        ema_slow = ema(closes, self.macd_slow)

        macd = ema_fast - ema_slow
        signal = ema(macd, self.macd_signal)
        hist = macd - signal

        return macd, signal, hist

    def _calculate_rsi(self, closes: np.ndarray) -> np.ndarray:
        """
        计算 RSI 指标 (纯 Python 实现)

        Returns:
            RSI 数组
        """
        delta = np.diff(closes)
        delta = np.insert(delta, 0, 0)  # 保持长度一致

        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)

        # 使用 Wilder 的平滑方法
        avg_gain = np.zeros(len(closes))
        avg_loss = np.zeros(len(closes))

        # 初始值 (第一个周期的平均)
        avg_gain[self.rsi_period - 1] = gain[:self.rsi_period].mean()
        avg_loss[self.rsi_period - 1] = loss[:self.rsi_period].mean()

        # Wilder 平滑
        for i in range(self.rsi_period, len(closes)):
            avg_gain[i] = (avg_gain[i-1] * (self.rsi_period - 1) + gain[i]) / self.rsi_period
            avg_loss[i] = (avg_loss[i-1] * (self.rsi_period - 1) + loss[i]) / self.rsi_period

        # 计算 RSI
        rsi = np.zeros(len(closes))
        for i in range(self.rsi_period - 1, len(closes)):
            if avg_loss[i] == 0:
                rsi[i] = 100
            else:
                rs = avg_gain[i] / avg_loss[i]
                rsi[i] = 100 - (100 / (1 + rs))

        return rsi

    def get_latest_values(self, df: pd.DataFrame) -> Dict[str, Optional[float]]:
        """
        获取最新的指标值

        Args:
            df: 包含指标的 DF

        Returns:
            指标值字典
        """
        if df.empty:
            return {
                "adx": None,
                "plus_di": None,
                "minus_di": None,
                "macd": None,
                "macd_signal": None,
                "macd_hist": None,
                "rsi": None,
            }

        last_row = df.iloc[-1]
        return {
            "adx": float(last_row["adx"]) if not np.isnan(last_row["adx"]) else None,
            "plus_di": (
                float(last_row["plus_di"])
                if not np.isnan(last_row["plus_di"])
                else None
            ),
            "minus_di": (
                float(last_row["minus_di"])
                if not np.isnan(last_row["minus_di"])
                else None
            ),
            "macd": float(last_row["macd"]) if not np.isnan(last_row["macd"]) else None,
            "macd_signal": (
                float(last_row["macd_signal"])
                if not np.isnan(last_row["macd_signal"])
                else None
            ),
            "macd_hist": (
                float(last_row["macd_hist"])
                if not np.isnan(last_row["macd_hist"])
                else None
            ),
            "rsi": float(last_row["rsi"]) if not np.isnan(last_row["rsi"]) else None,
        }

    def get_latest_adx(self, df: pd.DataFrame) -> Optional[float]:
        """获取最新 ADX 值"""
        values = self.get_latest_values(df)
        return values.get("adx")

    def get_latest_rsi(self, df: pd.DataFrame) -> Optional[float]:
        """获取最新 RSI 值"""
        values = self.get_latest_values(df)
        return values.get("rsi")

    def get_latest_macd(self, df: pd.DataFrame) -> Dict[str, Optional[float]]:
        """获取最新 MACD 值"""
        values = self.get_latest_values(df)
        return {
            "macd": values.get("macd"),
            "signal": values.get("macd_signal"),
            "hist": values.get("macd_hist"),
        }
