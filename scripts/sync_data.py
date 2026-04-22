#!/usr/bin/env python3
"""
市场数据同步脚本

功能:
- 从配置的数据源（local 或 binance）同步 OHLCV 数据
- 支持多时间周期：15m, 1h, 4h, 1d
- 数据按日期分割存储：{data_path}/{symbol}/{timeframe}/{symbol}-{timeframe}-{YYYY}-{MM}-{DD}.csv
- 数据缺失时自动补充（binance 源）或告警（local 源）
"""

import os
import sys
import time
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

# 导入 CSV 存储模块
from csv_storage import CsvStorage

# 加载环境变量
load_dotenv()

# 配置
DATA_SOURCE = os.getenv('DATA_SOURCE', 'binance')
DATA_PATH = Path(os.getenv('MARKET_RESEARCHER_DATA_PATH',
                           Path(__file__).parent.parent / 'data'))
BINANCE_API_BASE = os.getenv('BINANCE_API_BASE', 'https://api.binance.com')
WECOM_WEBHOOK_URL = os.getenv('WECOM_WEBHOOK_URL')
TOP_N = int(os.getenv('TOP_N', '10'))

# 初始化 CSV 存储
csv_storage = CsvStorage(str(DATA_PATH))

# 时间周期配置
TIMEFRAMES = {
    '1m': {'kline_interval': '1m', 'seconds': 60},
    '15m': {'kline_interval': '15m', 'seconds': 900},
    '1h': {'kline_interval': '1h', 'seconds': 3600},
    '4h': {'kline_interval': '4h', 'seconds': 14400},
    '1d': {'kline_interval': '1d', 'seconds': 86400},
}

# Top 交易对列表（从 .env 读取）
TOP_SYMBOLS = [s.strip() for s in os.getenv('TOP_SYMBOLS', '').split(',') if s.strip()]


def get_top_symbols_from_binance(n=10):
    """从 .env 配置获取 Top Symbols（不从 Binance 动态获取）"""
    if TOP_SYMBOLS:
        return TOP_SYMBOLS[:n]
    # 默认回退列表
    return [
        'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT',
        'DOGEUSDT', 'ADAUSDT', 'AVAXUSDT', 'TRXUSDT', 'LINKUSDT'
    ][:n]


def fetch_binance_klines(symbol, interval, start_time, end_time):
    """从 Binance 获取 K 线数据"""
    url = f"{BINANCE_API_BASE}/api/v3/klines"
    params = {
        'symbol': symbol,
        'interval': interval,
        'startTime': start_time,
        'endTime': end_time,
        'limit': 1000
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if not data:
            return pd.DataFrame()

        # 转换为 DataFrame
        df = pd.DataFrame(data, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_volume',
            'taker_quote_volume', 'ignore'
        ])

        # 转换数据类型
        df['timestamp'] = pd.to_datetime(df['timestamp'].astype(int), unit='ms')
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)

        return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
    except Exception as e:
        print(f"获取 {symbol} {interval} K 线失败：{e}")
        return pd.DataFrame()


def send_wecom_alert(message):
    """发送企业微信告警"""
    if not WECOM_WEBHOOK_URL:
        print("未配置 WECOM_WEBHOOK_URL，跳过告警")
        return

    try:
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": message
            }
        }
        response = requests.post(WECOM_WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
        print("企业微信告警发送成功")
    except Exception as e:
        print(f"发送企业微信告警失败：{e}")


def sync_symbol_binance(symbol, timeframe):
    """同步单个交易对的数据（Binance 源）"""
    config = TIMEFRAMES[timeframe]
    interval = config['kline_interval']

    # 计算需要获取的时间范围
    now = datetime.now(timezone.utc)
    end_time = int(now.timestamp() * 1000)

    # 获取已有数据的最后时间
    existing_df = csv_storage.load_recent(symbol, timeframe, limit=1)

    if not existing_df.empty:
        last_timestamp = existing_df['timestamp'].iloc[-1]
        start_time = int(last_timestamp.timestamp() * 1000) + config['seconds'] * 1000
    else:
        # 没有历史数据，获取最近 1000 根 K 线
        start_time = end_time - 1000 * config['seconds'] * 1000

    # 获取数据
    print(f"获取 {symbol} {timeframe} 数据...", end=' ')
    df = fetch_binance_klines(symbol, interval, start_time, end_time)

    if df.empty:
        print("未获取到新数据")
        return

    # 保存数据
    csv_storage.append(symbol, timeframe, df)
    print(f"保存 {len(df)} 条记录")


def sync_symbol_local(symbol, timeframe):
    """同步单个交易对的数据（local 源）"""
    # 检查数据是否存在
    df = csv_storage.load_recent(symbol, timeframe, limit=1)

    if df.empty:
        # 数据缺失，发送告警
        message = f"""## 市场数据缺失告警

- 交易对：{symbol}
- 时间周期：{timeframe}
- 缺失时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}
- 数据源：local

请检查数据是否已同步到 {DATA_PATH}。"""
        send_wecom_alert(message)
        return False

    print(f"  {symbol} {timeframe} 数据存在")
    return True


def sync_all_symbols(symbols=None):
    """同步 Top 交易对的数据

    Args:
        symbols: Optional list of symbols to sync. If None, syncs all TOP_SYMBOLS.
    """
    print(f"数据源：{DATA_SOURCE}")
    print(f"数据路径：{DATA_PATH}")

    if symbols is None:
        print(f"同步 TOP_SYMBOLS 配置的所有交易对...\n")
        symbols = get_top_symbols_from_binance()
        print(f"交易对列表：{', '.join(symbols)}\n")
    else:
        print(f"同步指定交易对：{', '.join(symbols)}\n")

    # 同步 1m 数据
    timeframe = '1m'
    print(f"\n=== 同步 {timeframe} 数据 ===")

    for i, symbol in enumerate(symbols, 1):
        try:
            print(f"[{i}/{len(symbols)}] {symbol}...", end=' ')
            if DATA_SOURCE == 'binance':
                sync_symbol_binance(symbol, timeframe)
            else:
                sync_symbol_local(symbol, timeframe)

            # 避免 API 限流
            if DATA_SOURCE == 'binance':
                time.sleep(0.1)
        except Exception as e:
            print(f"失败：{e}")

    print("\n数据同步完成")


def sync_single_symbol(symbol: str):
    """Sync 1m data for a single symbol from Binance

    Args:
        symbol: Trading pair symbol (e.g., 'BTCUSDT')
    """
    print(f"数据源：{DATA_SOURCE}")
    print(f"数据路径：{DATA_PATH}")
    print(f"同步 {symbol} 1m 数据...\n")

    timeframe = '1m'

    if DATA_SOURCE == 'binance':
        sync_symbol_binance(symbol, timeframe)
    else:
        sync_symbol_local(symbol, timeframe)

    print("\n数据同步完成")


def main():
    """主函数

    用法:
        python sync_data.py              # 同步所有 Top-N 交易对
        python sync_data.py BTCUSDT      # 同步单个交易对
    """
    import sys

    # Check for command-line argument
    if len(sys.argv) > 1:
        symbol = sys.argv[1]
        sync_single_symbol(symbol)
        return

    # Check for environment variable (called from analyze.py)
    sync_symbols = os.getenv('SYNC_SYMBOLS')
    if sync_symbols:
        symbols = [s.strip() for s in sync_symbols.split(',')]
        sync_all_symbols(symbols=symbols)
    else:
        sync_all_symbols()


if __name__ == '__main__':
    main()
