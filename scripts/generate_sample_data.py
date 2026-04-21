#!/usr/bin/env python3
"""
生成示例市场数据（用于测试）

当无法访问真实数据源时，生成模拟的 OHLCV 数据用于测试分析功能。
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DATA_PATH = Path(os.getenv('MARKET_RESEARCHER_DATA_PATH', 
                           Path(__file__).parent.parent / 'data'))

# 示例交易对
SAMPLE_SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT']

# 基础价格
BASE_PRICES = {
    'BTCUSDT': 65000,
    'ETHUSDT': 3500,
    'BNBUSDT': 580,
    'SOLUSDT': 150,
    'XRPUSDT': 0.62
}


def generate_ohlcv(symbol, timeframe, days=30):
    """生成模拟 OHLCV 数据"""
    base_price = BASE_PRICES.get(symbol, 100)
    
    # 时间周期对应的秒数
    timeframe_seconds = {
        '15m': 900,
        '1h': 3600,
        '4h': 14400,
        '1d': 86400
    }
    
    seconds = timeframe_seconds.get(timeframe, 3600)
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(days=days)
    
    # 生成时间序列
    timestamps = pd.date_range(start=start_time, end=now, freq=f'{seconds}s')
    n_points = len(timestamps)
    
    # 生成价格序列（随机游走）
    np.random.seed(hash(symbol) % 2**32)  # 可重复的随机性
    
    returns = np.random.normal(0, 0.02, n_points)  # 日收益率
    price_series = base_price * np.cumprod(1 + returns)
    
    # 生成 OHLCV
    data = []
    for i, ts in enumerate(timestamps):
        open_price = price_series[i]
        close_price = price_series[i] * (1 + np.random.uniform(-0.01, 0.01))
        high_price = max(open_price, close_price) * (1 + np.random.uniform(0, 0.005))
        low_price = min(open_price, close_price) * (1 - np.random.uniform(0, 0.005))
        volume = np.random.uniform(1000, 10000) * base_price / 1000
        
        data.append({
            'timestamp': int(ts.timestamp() * 1000),
            'open': round(open_price, 2),
            'high': round(high_price, 2),
            'low': round(low_price, 2),
            'close': round(close_price, 2),
            'volume': round(volume, 2)
        })
    
    return pd.DataFrame(data)


def generate_all_samples():
    """生成所有示例数据"""
    print("生成示例市场数据...\n")
    
    for symbol in SAMPLE_SYMBOLS:
        print(f"生成 {symbol} 数据...")
        
        for timeframe in ['15m', '1h', '4h', '1d']:
            df = generate_ohlcv(symbol, timeframe)
            
            # 保存
            dir_path = DATA_PATH / symbol
            dir_path.mkdir(parents=True, exist_ok=True)
            
            file_path = dir_path / f"{timeframe}.csv"
            df.to_csv(file_path, index=False)
            
            print(f"  {timeframe}: {len(df)} 条记录 → {file_path}")
    
    print("\n✅ 示例数据生成完成")


if __name__ == '__main__':
    generate_all_samples()
