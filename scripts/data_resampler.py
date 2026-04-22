#!/usr/bin/env python3
"""
数据重采样模块 - DataResampler

功能:
1. 接收 1m K 线数据
2. 自动 resample 成 5m/15m/1h/4h/1d 多周期
3. 每个周期独立 DF
4. 与 CsvStorage 集成，自动保存到每日文件
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta

import pandas as pd

from csv_storage import CsvStorage

logger = logging.getLogger(__name__)


class DataResampler:
    """
    数据重采样器

    将 1m K 线数据 resample 到多个时间周期
    """

    # 周期定义 (分钟数)
    TIMEFRAME_MINUTES = {
        "1m": 1,
        "5m": 5,
        "15m": 15,
        "1h": 60,
        "4h": 240,
        "1d": 1440,
    }

    def __init__(self, symbols: List[str], csv_storage: Optional[CsvStorage] = None):
        """
        初始化重采样器

        Args:
            symbols: 交易对列表
            csv_storage: CSV 存储实例 (可选)
        """
        self.symbols = symbols
        self.timeframes = list(self.TIMEFRAME_MINUTES.keys())
        self.csv_storage = csv_storage

        # 每个 symbol 的每个周期一个 DF
        # {symbol: {timeframe: df}}
        self._dfs: Dict[str, Dict[str, pd.DataFrame]] = {}

        for symbol in symbols:
            self._dfs[symbol] = {}
            for tf in self.timeframes:
                self._dfs[symbol][tf] = pd.DataFrame()

    def get_df(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """获取指定 symbol 和周期的 DF"""
        if symbol not in self._dfs:
            return None
        if timeframe not in self._dfs[symbol]:
            return None
        return self._dfs[symbol][timeframe]

    def get_all_dfs(self, symbol: str) -> Dict[str, pd.DataFrame]:
        """获取指定 symbol 的所有周期 DF"""
        return self._dfs.get(symbol, {})

    def load_from_storage(self, symbol: str, timeframe: str, limit: int = 1000) -> bool:
        """从 CSV 存储加载数据"""
        if self.csv_storage is None:
            logger.warning("未配置 csv_storage，无法加载数据")
            return False

        df = self.csv_storage.load_recent(symbol, timeframe, limit=limit)
        if df is not None and not df.empty:
            # 转换 timestamp 为 datetime 索引 (毫秒时间戳)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
            df = df.set_index('timestamp')
            self._dfs[symbol][timeframe] = df
            return True
        return False

    def load_all_from_storage(self, symbol: str, limit: int = 1000) -> bool:
        """从 CSV 存储加载某 symbol 的所有周期数据"""
        success = False
        for tf in self.timeframes:
            if self.load_from_storage(symbol, tf, limit=limit):
                success = True
        return success

    def update_1m(self, symbol: str, kline_1m: dict, save_to_storage: bool = True) -> Dict[str, bool]:
        """
        更新 1m K 线，并检查是否需要 resample

        Args:
            symbol: 交易对
            kline_1m: 1m K 线数据字典 {timestamp, open, high, low, close, volume}
            save_to_storage: 是否保存到 CSV 存储

        Returns:
            {timeframe: updated} 表示各周期是否更新
        """
        if symbol not in self._dfs:
            self._dfs[symbol] = {}
            for tf in self.timeframes:
                self._dfs[symbol][tf] = pd.DataFrame()

        # 将 1m K 线追加到 1m DF
        kline_df = pd.DataFrame([kline_1m])
        # 转换 timestamp 为 datetime，不强制时区（与现有数据保持一致）
        kline_df["timestamp"] = pd.to_datetime(kline_df["timestamp"])
        kline_df = kline_df.set_index("timestamp")

        # 确保列顺序
        for col in ["open", "high", "low", "close", "volume"]:
            if col not in kline_df.columns:
                kline_df[col] = 0.0

        # 追加到 1m DF
        if self._dfs[symbol]["1m"].empty:
            self._dfs[symbol]["1m"] = kline_df
        else:
            self._dfs[symbol]["1m"] = pd.concat([self._dfs[symbol]["1m"], kline_df])

        # 检查各周期是否需要更新
        updated = {"1m": True}  # 1m 总是更新

        for tf in self.timeframes[1:]:  # 跳过 1m
            if self._should_resample(symbol, tf):
                self._resample_to_timeframe(symbol, tf)
                updated[tf] = True
            else:
                updated[tf] = False

        # 保存到存储
        if save_to_storage and self.csv_storage is not None:
            for tf, is_updated in updated.items():
                if is_updated:
                    self._save_to_storage(symbol, tf)

        return updated

    def _save_to_storage(self, symbol: str, timeframe: str):
        """保存指定周期数据到 CSV 存储"""
        if self.csv_storage is None:
            return

        df = self._dfs[symbol][timeframe].copy()
        if df.empty:
            return

        # 重置索引，转换为标准格式
        df = df.reset_index()

        # timestamp 索引是 datetime，转为毫秒时间戳整数
        # 根据 datetime 分辨率选择正确的转换因子
        dtype_str = str(df['timestamp'].dtype)
        if 'ns' in dtype_str:
            # datetime64[ns] (纳秒) → 除以 10^6
            df['timestamp'] = df['timestamp'].astype('int64') // 10**6
        elif 'us' in dtype_str:
            # datetime64[us] (微秒) → 除以 1000
            df['timestamp'] = df['timestamp'].astype('int64') // 1000
        else:
            # datetime64[ms] (毫秒) → 直接使用
            df['timestamp'] = df['timestamp'].astype('int64')

        self.csv_storage.append(symbol, timeframe, df)

    def _should_resample(self, symbol: str, timeframe: str) -> bool:
        """
        判断是否应该 resample 到目标周期

        检查 1m DF 的最后一根 K 线是否到达目标周期的边界
        并且已经有足够的 1m 数据来形成完整的周期
        """
        if self._dfs[symbol]["1m"].empty:
            return False

        last_timestamp = self._dfs[symbol]["1m"].index[-1]
        if not self._is_boundary(last_timestamp, timeframe):
            return False

        # 检查是否有足够的 1m 数据来形成完整的周期
        target_minutes = self.TIMEFRAME_MINUTES[timeframe]
        period_end = last_timestamp
        period_start = self._get_period_start(period_end, timeframe)

        # 如果当前时间正好是周期边界，检查前一个完整周期
        actual_period_start = period_start - timedelta(minutes=target_minutes)

        # 统计前一个周期内的 1m K 线数量
        klines_in_period = len(
            self._dfs[symbol]["1m"][
                (self._dfs[symbol]["1m"].index >= actual_period_start)
                & (self._dfs[symbol]["1m"].index < period_end)
            ]
        )

        # 只有当 K 线数量等于周期分钟数时，才是完整的周期
        return klines_in_period >= target_minutes

    def _is_boundary(self, timestamp: datetime, timeframe: str) -> bool:
        """
        判断时间戳是否为目标周期的边界

        边界规则:
        - 5m: 分钟数为 0, 5, 10, 15, ...
        - 15m: 分钟数为 0, 15, 30, 45
        - 1h: 分钟数为 0
        - 4h: 分钟数为 0 且小时数为 0, 4, 8, 12, 16, 20
        - 1d: 分钟数为 0 且小时数为 0
        """
        minutes = timestamp.minute
        hours = timestamp.hour

        if timeframe == "5m":
            return minutes % 5 == 0
        elif timeframe == "15m":
            return minutes % 15 == 0
        elif timeframe == "1h":
            return minutes == 0
        elif timeframe == "4h":
            return minutes == 0 and hours % 4 == 0
        elif timeframe == "1d":
            return minutes == 0 and hours == 0
        else:
            return False

    def _get_period_start(self, timestamp: datetime, timeframe: str) -> datetime:
        """
        计算时间戳所在周期的开始时间

        例如:
        - timestamp=10:07, timeframe=5m → period_start=10:05
        - timestamp=10:30, timeframe=15m → period_start=10:30
        - timestamp=11:30, timeframe=1h → period_start=11:00
        """
        target_minutes = self.TIMEFRAME_MINUTES[timeframe]

        if timeframe == "5m":
            minute_offset = timestamp.minute % 5
            return timestamp.replace(
                minute=timestamp.minute - minute_offset, second=0, microsecond=0
            )
        elif timeframe == "15m":
            minute_offset = timestamp.minute % 15
            return timestamp.replace(
                minute=timestamp.minute - minute_offset, second=0, microsecond=0
            )
        elif timeframe == "1h":
            return timestamp.replace(minute=0, second=0, microsecond=0)
        elif timeframe == "4h":
            hour_offset = timestamp.hour % 4
            return timestamp.replace(
                hour=timestamp.hour - hour_offset, minute=0, second=0, microsecond=0
            )
        elif timeframe == "1d":
            return timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            return timestamp

    def _resample_to_timeframe(self, symbol: str, target_timeframe: str):
        """
        将 1m 数据 resample 到目标周期

        OHLCV 聚合规则:
        - open: first
        - high: max
        - low: min
        - close: last
        - volume: sum
        """
        df_1m = self._dfs[symbol]["1m"]

        if df_1m.empty:
            return

        # 获取目标周期的分钟数
        target_minutes = self.TIMEFRAME_MINUTES[target_timeframe]

        # 获取最后一根 K 线的时间戳（周期边界）
        last_timestamp = df_1m.index[-1]

        # 计算前一个完整周期的起止时间
        period_end = last_timestamp
        period_start = self._get_period_start(period_end, target_timeframe) - timedelta(
            minutes=target_minutes
        )

        # 只 resample 前一个完整周期的数据
        period_df = df_1m[(df_1m.index >= period_start) & (df_1m.index < period_end)]

        if len(period_df) < target_minutes:
            logger.debug(f"{symbol} {target_timeframe} 周期数据不足，跳过 resample")
            return

        # Resample OHLCV (使用前一个周期的开始时间作为 label)
        resampled = period_df.resample(
            f"{target_minutes}min",
            closed="left",
            label="left",  # 使用周期开始时间作为 label
        ).agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )

        # 删除全为 NaN 的行
        resampled = resampled.dropna()

        # 更新目标周期的 DF
        if self._dfs[symbol][target_timeframe].empty:
            self._dfs[symbol][target_timeframe] = resampled
        else:
            # 合并时避免重复
            existing_df = self._dfs[symbol][target_timeframe]
            if not existing_df.empty and resampled.index[0] <= existing_df.index[-1]:
                existing_df = existing_df[~existing_df.index.isin(resampled.index)]
            self._dfs[symbol][target_timeframe] = pd.concat([existing_df, resampled])

        logger.debug(
            f"{symbol} {target_timeframe} resample 完成，共 {len(self._dfs[symbol][target_timeframe])} 条"
        )

    def get_latest_kline(self, symbol: str, timeframe: str) -> Optional[dict]:
        """获取最新一根 K 线数据"""
        df = self.get_df(symbol, timeframe)
        if df is None or df.empty:
            return None

        last_row = df.iloc[-1]
        return {
            "timestamp": last_row.name,
            "open": last_row["open"],
            "high": last_row["high"],
            "low": last_row["low"],
            "close": last_row["close"],
            "volume": last_row["volume"],
        }
