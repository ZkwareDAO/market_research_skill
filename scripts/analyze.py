#!/usr/bin/env python3
"""
市场技术分析脚本

功能：
- 计算技术指标：RSI, MACD, Bollinger Bands, ATR, Volatility
- 判断市场趋势：trend_market/ranging_market, bullish/bearish/ranging
- 输出 Top 10 交易对的技术分析报告
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置
DATA_PATH = Path(os.getenv('MARKET_RESEARCHER_DATA_PATH', 
                           Path(__file__).parent.parent / 'data'))
OUTPUT_PATH = Path(__file__).parent.parent / 'output'
TOP_N = int(os.getenv('TOP_N', '10'))

# 技术指标参数
RSI_PERIOD = int(os.getenv('RSI_PERIOD', '14'))
MACD_FAST = int(os.getenv('MACD_FAST', '12'))
MACD_SLOW = int(os.getenv('MACD_SLOW', '26'))
MACD_SIGNAL = int(os.getenv('MACD_SIGNAL', '9'))
BB_PERIOD = int(os.getenv('BB_PERIOD', '20'))
BB_STD = float(os.getenv('BB_STD', '2'))
ATR_PERIOD = int(os.getenv('ATR_PERIOD', '14'))


def calculate_rsi(close, period=14):
    """计算 RSI 指标"""
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_macd(close, fast=12, slow=26, signal=9):
    """计算 MACD 指标"""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    
    return macd_line, signal_line, histogram


def calculate_bollinger_bands(close, period=20, std_dev=2):
    """计算布林带"""
    middle = close.rolling(window=period).mean()
    std = close.rolling(window=period).std()
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    
    return upper, middle, lower


def calculate_atr(high, low, close, period=14):
    """计算 ATR (平均真实波幅)"""
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    
    return atr


def calculate_volatility(close, period=20):
    """计算波动率（收益率的标准差）"""
    returns = close.pct_change()
    volatility = returns.rolling(window=period).std()
    return volatility


def analyze_symbol(symbol, timeframe):
    """分析单个交易对的技术指标"""
    file_path = DATA_PATH / symbol / f"{timeframe}.csv"
    
    if not file_path.exists():
        return None
    
    try:
        df = pd.read_csv(file_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        if len(df) < BB_PERIOD + 10:
            print(f"  {symbol} 数据不足，跳过")
            return None
        
        # 计算技术指标
        df['rsi'] = calculate_rsi(df['close'], RSI_PERIOD)
        df['macd'], df['macd_signal'], df['macd_hist'] = calculate_macd(
            df['close'], MACD_FAST, MACD_SLOW, MACD_SIGNAL
        )
        df['bb_upper'], df['bb_middle'], df['bb_lower'] = calculate_bollinger_bands(
            df['close'], BB_PERIOD, BB_STD
        )
        df['atr'] = calculate_atr(df['high'], df['low'], df['close'], ATR_PERIOD)
        df['volatility'] = calculate_volatility(df['close'], BB_PERIOD)
        
        # 获取最新数据
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        
        # 计算指标状态
        rsi_value = latest['rsi']
        macd_bullish = latest['macd'] > latest['macd_signal']
        macd_hist_positive = latest['macd_hist'] > 0
        
        # 布林带位置
        bb_position = '中轨'
        if latest['close'] > latest['bb_upper']:
            bb_position = '上轨外'
        elif latest['close'] > latest['bb_middle']:
            bb_position = '上轨侧'
        elif latest['close'] > latest['bb_lower']:
            bb_position = '下轨侧'
        else:
            bb_position = '下轨外'
        
        # 趋势判断
        trend = '震荡'
        if rsi_value > 50 and macd_bullish:
            trend = '偏多'
        elif rsi_value < 50 and not macd_bullish:
            trend = '偏空'
        
        # ATR 和波动率
        atr_value = latest['atr']
        volatility_pct = latest['volatility'] * 100 if pd.notna(latest['volatility']) else 0
        
        return {
            'symbol': symbol,
            'rsi': round(rsi_value, 2) if pd.notna(rsi_value) else None,
            'macd': 'bullish' if macd_bullish else 'bearish',
            'macd_hist': round(latest['macd_hist'], 4) if pd.notna(latest['macd_hist']) else None,
            'bb_position': bb_position,
            'atr': round(atr_value, 2) if pd.notna(atr_value) else None,
            'volatility': round(volatility_pct, 2),
            'trend': trend,
            'close': round(latest['close'], 2),
            'change_pct': round((latest['close'] - prev['close']) / prev['close'] * 100, 2)
        }
    except Exception as e:
        print(f"  分析 {symbol} 失败：{e}")
        return None


def get_symbols_for_timeframe(timeframe):
    """获取指定时间周期有数据的交易对列表"""
    symbols = []
    for item in DATA_PATH.iterdir():
        if item.is_dir():
            file_path = item / f"{timeframe}.csv"
            if file_path.exists():
                symbols.append(item.name)
    return symbols[:TOP_N]


def generate_report(timeframe):
    """生成技术分析报告"""
    print(f"\n生成 {timeframe} 技术分析报告...")
    
    # 获取交易对列表
    symbols = get_symbols_for_timeframe(timeframe)
    
    if not symbols:
        print(f"  未找到 {timeframe} 数据")
        return
    
    # 分析每个交易对
    results = []
    for symbol in symbols:
        print(f"  分析 {symbol}...")
        result = analyze_symbol(symbol, timeframe)
        if result:
            results.append(result)
    
    if not results:
        print("  没有可用的分析结果")
        return
    
    # 生成 Markdown 报告
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    report = f"""# 市场技术分析 - {timeframe} ({now})

## Top {len(results)} 交易对

| 排名 | 交易对 | 价格 | 24h 涨跌 | RSI | MACD | 布林带 | ATR | 波动率 | 趋势判断 |
|------|--------|------|---------|-----|------|--------|-----|--------|---------|
"""
    
    for i, r in enumerate(results, 1):
        report += f"| {i} | {r['symbol']} | {r['close']} | {r['change_pct']:+.2f}% | {r['rsi']} | {r['macd']} | {r['bb_position']} | {r['atr']} | {r['volatility']}% | {r['trend']} |\n"
    
    # 市场整体判断
    bullish_count = sum(1 for r in results if r['trend'] == '偏多')
    bearish_count = sum(1 for r in results if r['trend'] == '偏空')
    neutral_count = len(results) - bullish_count - bearish_count
    
    overall_trend = '震荡市'
    overall_direction = 'ranging'
    
    if bullish_count > bearish_count * 1.5:
        overall_trend = '趋势市场 - 牛市'
        overall_direction = 'bullish'
    elif bearish_count > bullish_count * 1.5:
        overall_trend = '趋势市场 - 熊市'
        overall_direction = 'bearish'
    
    avg_volatility = sum(r['volatility'] for r in results) / len(results)
    volatility_level = '高' if avg_volatility > 3 else ('中' if avg_volatility > 1.5 else '低')
    
    report += f"""
## 市场整体判断

- **趋势类型**: {overall_trend}
- **市场方向**: {overall_direction}
- **波动率水平**: {volatility_level} (平均 {avg_volatility:.2f}%)
- **多头占比**: {bullish_count}/{len(results)} ({bullish_count/len(results)*100:.1f}%)
- **空头占比**: {bearish_count}/{len(results)} ({bearish_count/len(results)*100:.1f}%)

## 详细指标

### RSI 分布
- 超买 (>70): {sum(1 for r in results if r['rsi'] and r['rsi'] > 70)} 个
- 中性 (30-70): {sum(1 for r in results if r['rsi'] and 30 <= r['rsi'] <= 70)} 个
- 超卖 (<30): {sum(1 for r in results if r['rsi'] and r['rsi'] < 30)} 个

### MACD 信号
- 看涨: {sum(1 for r in results if r['macd'] == 'bullish')} 个
- 看跌: {sum(1 for r in results if r['macd'] == 'bearish')} 个

---
*报告生成时间：{now}*
"""
    
    # 保存报告
    output_dir = OUTPUT_PATH / f"{timeframe}_analysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    filename = f"analysis_{now.replace(' ', '_').replace(':', '-')}.md"
    file_path = output_dir / filename
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"  报告已保存：{file_path}")
    
    # 输出到控制台
    print("\n" + "=" * 60)
    print(report)
    
    return results


def main():
    """主函数"""
    if len(sys.argv) > 1:
        timeframe = sys.argv[1]
        if timeframe not in ['15m', '1h', '4h', '1d']:
            print(f"错误：不支持的时间周期 {timeframe}")
            print("支持的时间周期：15m, 1h, 4h, 1d")
            sys.exit(1)
    else:
        # 默认执行 1h 分析
        timeframe = '1h'
    
    generate_report(timeframe)


if __name__ == '__main__':
    main()
