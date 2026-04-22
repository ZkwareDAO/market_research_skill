#!/usr/bin/env python3
"""
信号 DF 生成器 - SignalGenerator

功能:
合并所有周期的指标到一行，生成最终的信号 DF
"""

import logging
from typing import Dict, Optional, List

import pandas as pd
import numpy as np

try:
    from .market_judgment import MarketState
except ImportError:
    from market_judgment import MarketState

logger = logging.getLogger(__name__)


class SignalGenerator:
    """
    信号生成器

    输出 DF 列结构:
    - 基础 OHLCV (来自 1m)
    - 各周期指标: adx_1d, adx_4h, adx_1h, adx_15m, ...
    - MACD 各周期：macd_1d, macd_signal_1d, macd_hist_1d, ...
    - RSI 各周期：rsi_1d, rsi_4h, ...
    - 市场状态：market_type, direction
    """

    # 指标列表
    INDICATORS = [
        "adx",
        "plus_di",
        "minus_di",
        "macd",
        "macd_signal",
        "macd_hist",
        "rsi",
    ]

    # 周期列表
    TIMEFRAMES = ["1d", "4h", "1h", "15m", "5m", "1m"]

    def __init__(self, symbols: List[str], timeframes: Optional[List[str]] = None):
        """
        初始化信号生成器

        Args:
            symbols: 交易对列表
            timeframes: 周期列表
        """
        self.symbols = symbols
        self.timeframes = timeframes or self.TIMEFRAMES

    def generate(
        self,
        symbol: str,
        dfs_with_indicators: Dict[str, pd.DataFrame],
        market_state: MarketState,
    ) -> pd.DataFrame:
        """
        生成信号 DF

        Args:
            symbol: 交易对
            dfs_with_indicators: {timeframe: df_with_indicators}
            market_state: 市场状态

        Returns:
            信号 DF (每个 timestamp 一行，包含所有周期指标)
        """
        # 以 1m DF 为基础
        if "1m" not in dfs_with_indicators or dfs_with_indicators["1m"].empty:
            logger.warning(f"缺少 1m 数据，无法生成信号 DF: {symbol}")
            return pd.DataFrame()

        df_1m = dfs_with_indicators["1m"].copy()

        # 构建结果 DF
        result_df = df_1m[["open", "high", "low", "close", "volume"]].copy()

        # 为每个周期的每个指标添加列
        for tf in self.timeframes:
            if tf not in dfs_with_indicators:
                logger.debug(f"缺少周期 {tf} 的数据")
                continue

            df_tf = dfs_with_indicators[tf]
            if df_tf.empty:
                continue

            # 获取该周期的指标列
            for indicator in self.INDICATORS:
                if indicator in df_tf.columns:
                    col_name = f"{indicator}_{tf}"
                    # 将该周期的指标 reindex 到 1m 的时间索引
                    # 使用 forward fill，因为大周期的指标在小周期内保持不变
                    tf_values = df_tf[[indicator]].reindex(df_1m.index, method="ffill")
                    result_df[col_name] = tf_values[indicator].values

        # 添加市场状态列
        result_df["market_type"] = market_state.market_type
        result_df["direction"] = market_state.direction

        # 添加置信度
        result_df["confidence"] = market_state.confidence

        return result_df

    def generate_multi_symbol(
        self,
        all_symbols_dfs: Dict[str, Dict[str, pd.DataFrame]],
        all_symbols_states: Dict[str, MarketState],
    ) -> pd.DataFrame:
        """
        为多个交易对生成合并的信号 DF

        Args:
            all_symbols_dfs: {symbol: {timeframe: df}}
            all_symbols_states: {symbol: MarketState}

        Returns:
            合并的信号 DF (包含 symbol 列)
        """
        all_dfs = []

        for symbol in self.symbols:
            if symbol not in all_symbols_dfs:
                continue

            dfs = all_symbols_dfs[symbol]
            state = all_symbols_states.get(symbol, MarketState())

            signal_df = self.generate(symbol, dfs, state)

            if not signal_df.empty:
                signal_df["symbol"] = symbol
                all_dfs.append(signal_df)

        if not all_dfs:
            return pd.DataFrame()

        # 合并所有 symbol 的 DF
        result = pd.concat(all_dfs)

        # 重新排列列顺序
        base_cols = ["symbol", "open", "high", "low", "close", "volume"]
        indicator_cols = [c for c in result.columns if c not in base_cols]
        return result[base_cols + indicator_cols]

    def get_column_names(self) -> List[str]:
        """
        获取所有可能的列名

        Returns:
            列名列表
        """
        cols = ["timestamp", "open", "high", "low", "close", "volume", "symbol"]

        # 指标列
        for tf in self.timeframes:
            for indicator in self.INDICATORS:
                cols.append(f"{indicator}_{tf}")

        # 市场状态列
        cols.extend(["market_type", "direction", "confidence"])

        return cols
