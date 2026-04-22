#!/usr/bin/env python3
"""
CSV 存储管理模块 - CsvStorage

功能:
1. 每个交易对、每个周期、每天独立 CSV 文件
2. 文件路径：{data_path}/{symbol}/{timeframe}/{symbol}-{timeframe}-{YYYY}-{MM}-{DD}.csv
3. 支持增量写入和全量写入
4. 加载最近 N 条数据
"""

import logging
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime

import pandas as pd

logger = logging.getLogger(__name__)


class CsvStorage:
    """
    CSV 存储管理器

    文件命名规则:
    - {data_path}/{symbol}/{timeframe}/{symbol}-{timeframe}-{YYYY}-{MM}-{DD}.csv
    """

    def __init__(self, data_path: str, load_limit: int = 1000):
        """
        初始化 CSV 存储

        Args:
            data_path: 数据存储目录
            load_limit: 加载时最多读取的条数
        """
        self.data_path = Path(data_path)
        self.load_limit = load_limit
        self.data_path.mkdir(parents=True, exist_ok=True)

    def _get_date_str(self, timestamp=None) -> str:
        """获取日期字符串"""
        if timestamp is None:
            return datetime.now().strftime('%Y-%m-%d')

        # 处理毫秒时间戳（整数）
        if isinstance(timestamp, (int, float)):
            # 毫秒转纳秒
            return pd.Timestamp(timestamp * 10**6).strftime('%Y-%m-%d')

        return pd.Timestamp(timestamp).strftime('%Y-%m-%d')

    def _get_file_path(self, symbol: str, timeframe: str, date: Optional[str] = None) -> Path:
        """
        获取文件路径

        Args:
            symbol: 交易对
            timeframe: 周期
            date: 日期字符串 (YYYY-MM-DD)，默认使用当前日期

        Returns:
            文件路径
        """
        if date is None:
            date = self._get_date_str()

        # {data_path}/{symbol}/{timeframe}/{symbol}-{timeframe}-{YYYY}-{MM}-{DD}.csv
        dir_path = self.data_path / symbol / timeframe
        dir_path.mkdir(parents=True, exist_ok=True)

        file_name = f"{symbol}-{timeframe}-{date}.csv"
        return dir_path / file_name

    def get_file_path_for_timestamp(self, symbol: str, timeframe: str, timestamp) -> Path:
        """根据时间戳获取文件路径"""
        date = self._get_date_str(timestamp)
        return self._get_file_path(symbol, timeframe, date)

    def append(self, symbol: str, timeframe: str, df: pd.DataFrame) -> bool:
        """
        增量追加数据到 CSV

        Args:
            symbol: 交易对
            timeframe: 周期
            df: 要追加的 DF (必须有 timestamp 列)

        Returns:
            是否成功
        """
        if df.empty:
            return True

        # 按日期分组写入
        df['date'] = df['timestamp'].apply(self._get_date_str)

        for date, date_df in df.groupby('date'):
            file_path = self._get_file_path(symbol, timeframe, date)

            try:
                # 检查文件是否存在
                if file_path.exists():
                    existing = pd.read_csv(file_path)
                    if not existing.empty:
                        # 检查最后一条数据是否相同
                        last_ts = existing['timestamp'].iloc[-1]
                        new_df = date_df[~date_df['timestamp'].isin(existing['timestamp'])]
                        if new_df.empty:
                            continue  # 数据已存在，跳过
                        # 追加新数据
                        combined = pd.concat([existing, new_df]).drop_duplicates(
                            subset=['timestamp'], keep='last'
                        )
                        combined.to_csv(file_path, index=False)
                    else:
                        date_df.drop(columns=['date']).to_csv(file_path, index=False)
                else:
                    date_df.drop(columns=['date']).to_csv(file_path, index=False)

            except Exception as e:
                logger.error(f"追加 CSV 失败 {symbol} {timeframe} {date}: {e}")
                return False

        return True

    def save_full(self, symbol: str, timeframe: str, df: pd.DataFrame) -> bool:
        """
        全量保存 DF 到 CSV（按日期分割）

        Args:
            symbol: 交易对
            timeframe: 周期
            df: 要保存的 DF

        Returns:
            是否成功
        """
        if df.empty:
            return True

        # 按日期分组写入
        df['date'] = df['timestamp'].apply(self._get_date_str)

        for date, date_df in df.groupby('date'):
            file_path = self._get_file_path(symbol, timeframe, date)
            try:
                date_df.drop(columns=['date']).to_csv(file_path, index=False)
            except Exception as e:
                logger.error(f"保存 CSV 失败 {symbol} {timeframe} {date}: {e}")
                return False

        return True

    def load_recent(self, symbol: str, timeframe: str, limit: Optional[int] = None) -> pd.DataFrame:
        """
        加载最近 N 条数据（从所有日期的文件中）

        Args:
            symbol: 交易对
            timeframe: 周期
            limit: 最多读取的条数，默认使用 self.load_limit

        Returns:
            最近 N 条数据的 DF，如果文件不存在返回空 DF
        """
        limit = limit or self.load_limit

        # 获取该 symbol/timeframe 的所有文件
        dir_path = self.data_path / symbol / timeframe
        if not dir_path.exists():
            return pd.DataFrame()

        # 按文件名排序（日期倒序）
        files = sorted(dir_path.glob(f"{symbol}-{timeframe}-*.csv"), reverse=True)

        if not files:
            return pd.DataFrame()

        # 读取所有文件并合并
        all_dfs = []
        total_rows = 0

        # CSV 文件列定义
        csv_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume',
                       'close_time', 'quote_volume', 'trades', 'taker_buy_volume',
                       'taker_quote_volume', 'ignore']

        for f in files:
            try:
                # 检查文件是否有表头
                with open(f, 'r') as fp:
                    first_line = fp.readline().strip()
                    # 表头检测：只有当第一行包含列名 'timestamp' 时才是表头
                    # 日期格式的数据行如 "2020-07-08" 或 "2026-04-11 00:00:00" 不是表头
                    has_header = first_line == 'timestamp,open,high,low,close,volume' or \
                                 first_line.startswith('timestamp,')

                if has_header:
                    df = pd.read_csv(f)
                else:
                    df = pd.read_csv(f, names=csv_columns)

                all_dfs.append(df)
                total_rows += len(df)
                if total_rows >= limit:
                    break
            except Exception as e:
                logger.error(f"加载 CSV 失败 {f}: {e}")
                continue

        if not all_dfs:
            return pd.DataFrame()

        # 合并并按 timestamp 排序
        combined = pd.concat(all_dfs).drop_duplicates(
            subset=['timestamp'], keep='last'
        )

        # 统一转换 timestamp 为 datetime（处理日期字符串和毫秒时间戳混合的情况）
        def convert_timestamp(ts):
            try:
                if isinstance(ts, str):
                    # 日期字符串格式：2023-07-28 或 2026-04-11 00:00:00
                    return pd.to_datetime(ts)
                elif isinstance(ts, (int, float)):
                    # 毫秒时间戳
                    return pd.to_datetime(ts, unit='ms')
                else:
                    return ts
            except Exception:
                # 无法转换的值返回 NaT
                return pd.NaT

        combined['timestamp'] = combined['timestamp'].apply(convert_timestamp)
        combined = combined.dropna(subset=['timestamp']).sort_values('timestamp')

        # 返回最后 N 条
        return combined.iloc[-limit:]

    def load_all(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """
        加载全部数据

        Args:
            symbol: 交易对
            timeframe: 周期

        Returns:
            全部数据的 DF，如果文件不存在返回空 DF
        """
        dir_path = self.data_path / symbol / timeframe
        if not dir_path.exists():
            return pd.DataFrame()

        # 获取所有文件
        files = list(dir_path.glob(f"{symbol}-{timeframe}-*.csv"))

        if not files:
            return pd.DataFrame()

        # 读取所有文件并合并
        all_dfs = []
        for f in files:
            try:
                df = pd.read_csv(f)
                all_dfs.append(df)
            except Exception as e:
                logger.error(f"加载 CSV 失败 {f}: {e}")
                continue

        if not all_dfs:
            return pd.DataFrame()

        # 合并并按 timestamp 排序
        return pd.concat(all_dfs).drop_duplicates(
            subset=['timestamp'], keep='last'
        ).sort_values('timestamp')

    def list_symbols(self) -> List[str]:
        """列出所有有数据的交易对"""
        symbols = set()
        for d in self.data_path.iterdir():
            if d.is_dir():
                symbols.add(d.name)
        return sorted(list(symbols))

    def list_timeframes(self, symbol: str) -> List[str]:
        """列出某个交易对有哪些周期的数据"""
        symbol_path = self.data_path / symbol
        if not symbol_path.exists():
            return []

        timeframes = set()
        for d in symbol_path.iterdir():
            if d.is_dir():
                timeframes.add(d.name)
        return sorted(list(timeframes))

    def list_dates(self, symbol: str, timeframe: str) -> List[str]:
        """列出某个交易对周期有哪些日期的数据"""
        dir_path = self.data_path / symbol / timeframe
        if not dir_path.exists():
            return []

        dates = set()
        for f in dir_path.glob(f"{symbol}-{timeframe}-*.csv"):
            # 从文件名提取日期
            parts = f.stem.split('-')
            if len(parts) >= 3:
                # {symbol}-{timeframe}-{YYYY}-{MM}-{DD}
                date = '-'.join(parts[-3:])
                dates.add(date)
        return sorted(list(dates))
