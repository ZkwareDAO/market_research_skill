#!/usr/bin/env python3
"""
市场数据同步脚本

功能：
- 从配置的数据源（zkware 或 binance）同步 OHLCV 数据
- 支持多时间周期：15m, 1h, 4h, 1d
- 数据缺失时自动补充（binance 源）或告警（zkware 源）
"""

import os
import sys
import time
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置
DATA_SOURCE = os.getenv('DATA_SOURCE', 'binance')
DATA_PATH = Path(os.getenv('MARKET_RESEARCHER_DATA_PATH', 
                           Path(__file__).parent.parent / 'data'))
BINANCE_API_BASE = os.getenv('BINANCE_API_BASE', 'https://api.binance.com')
WECOM_WEBHOOK_URL = os.getenv('WECOM_WEBHOOK_URL')
TOP_N = int(os.getenv('TOP_N', '10'))

# 时间周期配置
TIMEFRAMES = {
    '15m': {'kline_interval': '15m', 'seconds': 900},
    '1h': {'kline_interval': '1h', 'seconds': 3600},
    '4h': {'kline_interval': '4h', 'seconds': 14400},
    '1d': {'kline_interval': '1d', 'seconds': 86400},
}

# Top 交易对列表（按成交量排序）
TOP_SYMBOLS = [
    'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT',
    'DOGEUSDT', 'ADAUSDT', 'AVAXUSDT', 'TRXUSDT', 'LINKUSDT'
]


def get_top_symbols_from_binance(n=10):
    """从 Binance 获取成交量前 N 的交易对"""
    try:
        url = f"{BINANCE_API_BASE}/api/v3/ticker/24hr"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # 过滤 USDT 交易对并按成交量排序
        usdt_pairs = [item for item in data if item['symbol'].endswith('USDT')]
        sorted_pairs = sorted(usdt_pairs, key=lambda x: float(x['quoteVolume']), reverse=True)
        
        return [item['symbol'] for item in sorted_pairs[:n]]
    except Exception as e:
        print(f"获取 Top 交易对失败：{e}")
        return TOP_SYMBOLS[:n]


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


def load_existing_data(symbol, timeframe):
    """加载已存在的 CSV 数据"""
    file_path = DATA_PATH / symbol / f"{timeframe}.csv"
    if file_path.exists():
        try:
            df = pd.read_csv(file_path)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df
        except Exception as e:
            print(f"读取 {file_path} 失败：{e}")
    return pd.DataFrame()


def save_data(symbol, timeframe, df):
    """保存数据到 CSV"""
    if df.empty:
        return
    
    dir_path = DATA_PATH / symbol
    dir_path.mkdir(parents=True, exist_ok=True)
    
    file_path = dir_path / f"{timeframe}.csv"
    
    # 合并已有数据
    existing_df = load_existing_data(symbol, timeframe)
    
    if not existing_df.empty:
        # 去重并排序
        combined_df = pd.concat([existing_df, df]).drop_duplicates(
            subset=['timestamp'], keep='last'
        ).sort_values('timestamp')
    else:
        combined_df = df.sort_values('timestamp')
    
    # 保存
    combined_df.to_csv(file_path, index=False)
    print(f"保存 {symbol} {timeframe} 数据，共 {len(combined_df)} 条记录")


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
    existing_df = load_existing_data(symbol, timeframe)
    
    if not existing_df.empty:
        last_timestamp = existing_df['timestamp'].max()
        start_time = int(last_timestamp.timestamp() * 1000) + config['seconds'] * 1000
    else:
        # 没有历史数据，获取最近 1000 根 K 线
        start_time = end_time - 1000 * config['seconds'] * 1000
    
    # 获取数据
    print(f"获取 {symbol} {timeframe} 数据...")
    df = fetch_binance_klines(symbol, interval, start_time, end_time)
    
    if df.empty:
        print(f"  未获取到新数据")
        return
    
    # 保存数据
    save_data(symbol, timeframe, df)


def sync_symbol_zkware(symbol, timeframe):
    """同步单个交易对的数据（zkware 源）"""
    # TODO: 实现 zkware 数据源同步
    # 目前从 sync_market_data_skill 同步的数据目录读取
    file_path = DATA_PATH / symbol / f"{timeframe}.csv"
    
    if not file_path.exists():
        # 数据缺失，发送告警
        message = f"""## 市场数据缺失告警

- 交易对：{symbol}
- 时间周期：{timeframe}
- 缺失时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}
- 数据源：zkware

请检查 sync_market_data_skill 是否正常运行。"""
        send_wecom_alert(message)
        return False
    
    print(f"  {symbol} {timeframe} 数据存在")
    return True


def sync_all_symbols():
    """同步所有 Top 交易对的数据"""
    print(f"数据源：{DATA_SOURCE}")
    print(f"数据路径：{DATA_PATH}")
    print(f"同步 Top {TOP_N} 交易对...\n")
    
    # 获取 Top 交易对列表
    if DATA_SOURCE == 'binance':
        try:
            symbols = get_top_symbols_from_binance(TOP_N)
        except Exception as e:
            print(f"⚠️  无法从 Binance 获取交易对列表：{e}")
            print("使用默认交易对列表\n")
            symbols = TOP_SYMBOLS[:TOP_N]
    else:
        symbols = TOP_SYMBOLS[:TOP_N]
    
    print(f"交易对列表：{', '.join(symbols[:5])}...")
    
    # 同步每个时间周期
    for timeframe in TIMEFRAMES.keys():
        print(f"\n=== 同步 {timeframe} 数据 ===")
        
        for i, symbol in enumerate(symbols, 1):
            try:
                print(f"[{i}/{len(symbols)}] {symbol}...", end=' ')
                if DATA_SOURCE == 'binance':
                    sync_symbol_binance(symbol, timeframe)
                else:
                    sync_symbol_zkware(symbol, timeframe)
                
                # 避免 API 限流
                if DATA_SOURCE == 'binance':
                    time.sleep(0.2)
            except Exception as e:
                print(f"失败：{e}")
    
    print("\n✅ 数据同步完成")


if __name__ == '__main__':
    sync_all_symbols()
