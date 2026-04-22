#!/usr/bin/env python3
"""
市场技术分析脚本 - 增强版

功能:
- 支持单 symbol 分析：python analyze.py 1h BTCUSDT
- 自动从 1m数据 resample 生成其他周期
- 支持 local/binance 数据源配置
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import talib as ta

# 导入 CSV 存储模块
from csv_storage import CsvStorage
from data_resampler import DataResampler

# 加载环境变量
load_dotenv()

# 配置
DATA_SOURCE = os.getenv('DATA_SOURCE', 'binance')
DATA_PATH = Path(os.getenv('MARKET_RESEARCHER_DATA_PATH',
                           Path(__file__).parent.parent / 'data'))
OUTPUT_PATH = Path(os.getenv('OUTPUT_PATH', Path(__file__).parent.parent / 'output'))
TOP_N = int(os.getenv('TOP_N', '10'))

# Top Symbols 列表（从 .env 读取）
TOP_SYMBOLS = [s.strip() for s in os.getenv('TOP_SYMBOLS', '').split(',') if s.strip()]
if not TOP_SYMBOLS:
    TOP_SYMBOLS = [
        'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT',
        'DOGEUSDT', 'ADAUSDT', 'AVAXUSDT', 'DOTUSDT', 'MATICUSDT'
    ]

# 时间周期配置（用于 resample）
TIMEFRAMES = ['15m', '1h', '4h', '1d']

# 各周期生成 30 条输出所需的 1m数据条数
TIMEFRAME_1M_REQUIREMENTS = {
    '15m': 450,      # 30 * 15
    '1h': 1800,      # 30 * 60
    '4h': 7200,      # 30 * 240
    '1d': 43200,     # 30 * 1440
}

# 初始化 CSV 存储
csv_storage = CsvStorage(str(DATA_PATH))

# 技术指标参数
RSI_PERIOD = int(os.getenv('RSI_PERIOD', '14'))
MACD_FAST = int(os.getenv('MACD_FAST', '12'))
MACD_SLOW = int(os.getenv('MACD_SLOW', '26'))
MACD_SIGNAL = int(os.getenv('MACD_SIGNAL', '9'))
BB_PERIOD = int(os.getenv('BB_PERIOD', '20'))
BB_STD = float(os.getenv('BB_STD', '2'))
ATR_PERIOD = int(os.getenv('ATR_PERIOD', '14'))


def sync_symbol_data(symbol: str) -> bool:
    """
    Sync 1m data for a single symbol from Binance.

    Args:
        symbol: Trading pair symbol (e.g., 'BTCUSDT')

    Returns:
        True if sync successful, False otherwise
    """
    if DATA_SOURCE != 'binance':
        return False

    # Import sync function from sync_data module
    from sync_data import sync_symbol_binance, csv_storage

    try:
        print(f"  同步 {symbol} 1m 数据...", end=' ')
        sync_symbol_binance(symbol, '1m')
        return True
    except Exception as e:
        print(f"失败：{e}")
        return False


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


def calculate_volatility(close, period=20, timeframe='1h'):
    """
    计算年化波动率（历史波动率 HV）

    公式：HV = std(收益率) × √(年化系数) × 100
    """
    returns = close.pct_change()

    # 年化系数（基于日历日，加密货币 7×24 交易）
    annualization_factors = {
        '1d': 365,
        '4h': 365 * 6,
        '1h': 365 * 24,
        '15m': 365 * 24 * 4,
        '5m': 365 * 24 * 12,
        '1m': 365 * 24 * 60,
    }

    factor = annualization_factors.get(timeframe, 365 * 24)
    volatility = returns.rolling(window=period).std() * np.sqrt(factor) * 100
    return volatility


def analyze_symbol(symbol, timeframe):
    """分析单个交易对的技术指标"""
    # 从 CSV 存储加载数据
    df = csv_storage.load_recent(symbol, timeframe, limit=1000)

    if df.empty:
        return None

    try:
        # 确保 timestamp 是 datetime 类型
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # 检查数据是否足够
        min_bars = BB_PERIOD + 10
        if len(df) < min_bars:
            print(f"  {symbol} 数据不足（需要{min_bars}条，实际{len(df)}条），跳过")
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
        df['volatility'] = calculate_volatility(df['close'], BB_PERIOD, timeframe)

        # 使用 ta-lib 计算 ADX 和 DI
        df['adx'] = ta.ADX(df['high'], df['low'], df['close'], timeperiod=14)
        df['plus_di'] = ta.PLUS_DI(df['high'], df['low'], df['close'], timeperiod=14)
        df['minus_di'] = ta.MINUS_DI(df['high'], df['low'], df['close'], timeperiod=14)

        # 获取最新数据
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest

        # 计算指标状态
        rsi_value = latest['rsi']
        macd_bullish = latest['macd'] > latest['macd_signal']

        # 布林带位置
        bb_position = '中轨'
        if pd.notna(latest['bb_upper']) and latest['close'] > latest['bb_upper']:
            bb_position = '上轨外'
        elif pd.notna(latest['bb_middle']) and latest['close'] > latest['bb_middle']:
            bb_position = '上轨侧'
        elif pd.notna(latest['bb_lower']) and latest['close'] > latest['bb_lower']:
            bb_position = '下轨侧'
        else:
            bb_position = '下轨外'

        # 价格趋势：基于 ADX
        price_trend = '震荡市场'
        if pd.notna(latest['adx']) and latest['adx'] >= 25:
            price_trend = '趋势市场'

        # 运行方向：基于 +DI 和 -DI
        direction = 'bearish'
        if pd.notna(latest['plus_di']) and pd.notna(latest['minus_di']):
            if latest['plus_di'] > latest['minus_di']:
                direction = 'bullish'

        # ATR 和波动率
        atr_value = latest['atr'] if pd.notna(latest['atr']) else None
        volatility_pct = latest['volatility'] if pd.notna(latest['volatility']) else 0

        return {
            'symbol': symbol,
            'rsi': round(rsi_value, 2) if pd.notna(rsi_value) else None,
            'macd': 'bullish' if macd_bullish else 'bearish',
            'macd_hist': round(latest['macd_hist'], 4) if pd.notna(latest['macd_hist']) else None,
            'adx': round(latest['adx'], 2) if pd.notna(latest['adx']) else None,
            'direction': direction,
            'price_trend': price_trend,
            'bb_position': bb_position,
            'atr': round(atr_value, 2) if atr_value else None,
            'volatility': round(volatility_pct, 2),
            'close': round(latest['close'], 2),
            'change_pct': round((latest['close'] - prev['close']) / prev['close'] * 100, 2)
        }
    except Exception as e:
        print(f"  分析 {symbol} 失败：{e}")
        return None


def ensure_data_exists(symbol: str, timeframe: str, auto_sync: bool = True) -> bool:
    """
    Ensure data exists for symbol and timeframe.
    If not, try to resample from 1m (batch resample all data).
    Skip Binance sync when DATA_SOURCE is 'local'.

    Returns:
        True if data available, False otherwise
    """
    print(f"  检查 {symbol} {timeframe} 数据...", end=' ')

    # Step 1: Check if requested timeframe data exists and has enough bars
    df = csv_storage.load_recent(symbol, timeframe, limit=30)
    if not df.empty and len(df) >= 30:
        print(f"已存在 ({len(df)} 条)")
        return True

    # If data exists but less than 30 bars, we need to resample from 1m
    if not df.empty:
        print(f"数据不足 ({len(df)} 条)", end=' → ')
    else:
        print("不存在", end=' → ')

    # Step 2: Check if 1m data exists
    # Get required 1m bars for minimum 30 output bars
    required_1m_bars = TIMEFRAME_1M_REQUIREMENTS.get(timeframe, 1000)
    df_1m = csv_storage.load_recent(symbol, '1m', limit=required_1m_bars)
    if not df_1m.empty:
        print(f"1m数据存在 ({len(df_1m)} 条) → 准备批量重采样")
        print("从 1m 批量重采样...", end=' ')
        try:
            # 批量 resample 所有 1m数据到目标周期
            resampler = DataResampler([symbol], csv_storage)
            resampler.load_from_storage(symbol, '1m', limit=required_1m_bars)

            df_1m_full = resampler.get_df(symbol, '1m')
            if df_1m_full is None or df_1m_full.empty:
                print("1m数据为空")
                return False

            # Check if we have enough 1m data for 30 output bars
            actual_1m_bars = len(df_1m_full)
            if actual_1m_bars < required_1m_bars:
                # Calculate max possible output bars
                minutes_per_bar = TIMEFRAME_1M_REQUIREMENTS.get(timeframe, 1440) // 30
                max_output_bars = actual_1m_bars // minutes_per_bar
                print(f"1m数据不足（需要 {required_1m_bars} 条，实际 {actual_1m_bars} 条），预计生成约 {max_output_bars} 条")
                # Continue with available data, don't return False

            # 批量 resample
            ohlc_dict = {
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }
            df_resampled = df_1m_full.resample(timeframe, closed='left', label='left').agg(ohlc_dict).dropna()

            if len(df_resampled) == 0:
                print("重采样失败（无完整周期）")
                return False

            # Keep only the latest 30 bars
            if len(df_resampled) > 30:
                df_resampled = df_resampled.iloc[-30:]

            # 保存到 CSV
            resampler._dfs[symbol][timeframe] = df_resampled
            resampler._save_to_storage(symbol, timeframe)

            print(f"完成 (生成 {len(df_resampled)} 条)")
            return True
        except Exception as e:
            print(f"重采样失败：{e}")
            return False

    # Step 3: No 1m data
    if auto_sync and DATA_SOURCE == "binance":
        print("1m 数据不存在 → 同步 1m 数据...")
        if sync_symbol_data(symbol):
            return ensure_data_exists(symbol, timeframe, auto_sync=False)
        return False
    else:
        print("无法获取数据（local 源无 1m数据）")
        return False


def get_symbols_for_timeframe(timeframe, symbol_filter=None):
    """获取指定时间周期有数据的交易对列表"""
    if symbol_filter:
        # 单 symbol 模式
        if ensure_data_exists(symbol_filter, timeframe):
            return [symbol_filter]
        return []

    # 全量模式
    symbols = csv_storage.list_symbols()

    # 过滤出有该 timeframe 数据的 symbol
    valid_symbols = []
    for symbol in symbols:
        timeframes = csv_storage.list_timeframes(symbol)
        if timeframe in timeframes:
            valid_symbols.append(symbol)

    return sorted(valid_symbols)[:TOP_N]


def generate_report(timeframe, symbol_filter=None, batch_symbols=None):
    """生成技术分析报告"""
    if batch_symbols is not None:
        print(f"\n批量模式：分析 {len(batch_symbols)} 个 symbol 的 {timeframe} 数据")
    elif symbol_filter:
        print(f"\n单符号模式：分析 {symbol_filter} {timeframe}")
    else:
        print(f"\n全量模式：分析所有 symbol 的 {timeframe} 数据")

    # 获取交易对列表
    if batch_symbols is not None:
        # 批量模式：使用指定的 symbol 列表
        symbols = batch_symbols
    elif symbol_filter:
        # 单符号模式
        symbols = get_symbols_for_timeframe(timeframe, symbol_filter)
    else:
        # 全量模式：从 csv_storage 获取
        symbols = get_symbols_for_timeframe(timeframe)

    if not symbols:
        if symbol_filter:
            print(f"  未找到 {symbol_filter} {timeframe} 数据，且无法自动获取")
        elif batch_symbols is not None:
            print(f"  未找到任何 symbol 的 {timeframe} 数据")
        else:
            print(f"  未找到 {timeframe} 数据")
        return

    # 分析每个交易对
    results = []
    for symbol in symbols:
        print(f"  分析 {symbol}...", end=' ')
        result = analyze_symbol(symbol, timeframe)
        if result:
            results.append(result)
            print(f"完成")
        else:
            print(f"跳过")

    if not results:
        print("  没有可用的分析结果")
        return

    # 生成 Markdown 报告
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    report = f"""# 市场技术分析 - {timeframe} ({now})

## Top {len(results)} 交易对

| 排名 | 交易对 | 价格 | 24h 涨跌 | RSI | MACD | ADX | 布林带 | ATR | 波动率 | 运行方向 | 价格趋势 |
|------|--------|------|---------|-----|------|-----|--------|-----|--------|----------|----------|
"""

    for i, r in enumerate(results, 1):
        adx_str = str(r['adx']) if r['adx'] else 'N/A'
        report += f"| {i} | {r['symbol']} | {r['close']} | {r['change_pct']:+.2f}% | {r['rsi']} | {r['macd']} | {adx_str} | {r['bb_position']} | {r['atr']} | {r['volatility']}% | {r['direction']} | {r['price_trend']} |\n"

    # 市场整体判断
    # 统计趋势市场数量
    trending_count = sum(1 for r in results if r['price_trend'] == '趋势市场')
    # 统计运行方向
    bullish_count = sum(1 for r in results if r['direction'] == 'bullish')
    bearish_count = sum(1 for r in results if r['direction'] == 'bearish')

    overall_trend = '震荡市场'
    overall_direction = 'ranging'

    if trending_count > len(results) * 0.5:
        overall_trend = '趋势市场'

    if bullish_count > bearish_count * 1.5:
        overall_direction = 'bullish'
    elif bearish_count > bullish_count * 1.5:
        overall_direction = 'bearish'

    avg_volatility = sum(r['volatility'] for r in results) / len(results)
    volatility_level = '高' if avg_volatility > 3 else ('中' if avg_volatility > 1.5 else '低')

    report += f"""
## 市场整体判断

- **市场类型**: {overall_trend} (趋势市场占比 {trending_count}/{len(results)} = {trending_count/len(results)*100:.1f}%)
- **运行方向**: {overall_direction}
- **波动率水平**: {volatility_level} (平均 {avg_volatility:.2f}%)
- **bullish 占比**: {bullish_count}/{len(results)} ({bullish_count/len(results)*100:.1f}%)
- **bearish 占比**: {bearish_count}/{len(results)} ({bearish_count/len(results)*100:.1f}%)

## 详细指标

### ADX 分布
- 趋势市场 (ADX >= 25): {sum(1 for r in results if r['adx'] and r['adx'] >= 25)} 个
- 震荡市场 (ADX < 25): {sum(1 for r in results if r['adx'] and r['adx'] < 25)} 个
- 无数据：{sum(1 for r in results if not r['adx'])} 个

### RSI 分布
- 超买 (>70): {sum(1 for r in results if r['rsi'] and r['rsi'] > 70)} 个
- 中性 (30-70): {sum(1 for r in results if r['rsi'] and 30 <= r['rsi'] <= 70)} 个
- 超卖 (<30): {sum(1 for r in results if r['rsi'] and r['rsi'] < 30)} 个

### MACD 信号
- 看涨：{sum(1 for r in results if r['macd'] == 'bullish')} 个
- 看跌：{sum(1 for r in results if r['macd'] == 'bearish')} 个

### 运行方向统计
- bullish (+DI > -DI): {bullish_count} 个
- bearish (+DI < -DI): {bearish_count} 个

---
*报告生成时间：{now}*
"""

    # 保存报告 - 按 symbol 输出到独立目录
    # 批量模式：每个 symbol 输出到 {OUTPUT_PATH}/{symbol}/{timeframe}_analysis/
    # 单符号模式：输出到 {OUTPUT_PATH}/{symbol}/{timeframe}_analysis/
    # 全量模式：输出到 {OUTPUT_PATH}/all/{timeframe}_analysis/
    if len(symbols) == 1 or symbol_filter:
        # 单符号模式
        output_dir = OUTPUT_PATH / symbols[0] / f"{timeframe}_analysis"
    else:
        # 批量模式：所有 symbol 汇总报告
        output_dir = OUTPUT_PATH / "all" / f"{timeframe}_analysis"
    
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
    """主函数

    用法:
        python analyze_enhanced.py                    # 默认 1h 批量分析 TOP_SYMBOLS
        python analyze_enhanced.py 1h                 # 1h 批量分析 TOP_SYMBOLS
        python analyze_enhanced.py 1h BTCUSDT         # 1h 分析单个 BTCUSDT
        python analyze_enhanced.py 4h ETHUSDT         # 4h 分析 ETHUSDT（自动 resample）
        python analyze_enhanced.py 1h --batch         # 显式批量模式
        python analyze_enhanced.py 1h --all           # 分析所有可用 symbol
    """
    if len(sys.argv) > 1:
        timeframe = sys.argv[1]
        if timeframe not in ['15m', '1h', '4h', '1d']:
            print(f"错误：不支持的时间周期 {timeframe}")
            print("支持的时间周期：15m, 1h, 4h, 1d")
            sys.exit(1)

        # 检查是否有 --batch 或 --all 标志
        batch_mode = '--batch' in sys.argv or '--all' in sys.argv
        all_symbols = '--all' in sys.argv

        # 可选的 symbol 参数
        symbol = None
        if len(sys.argv) > 2 and sys.argv[2] not in ['--batch', '--all']:
            symbol = sys.argv[2]

        if symbol and not batch_mode:
            # 单符号模式
            print(f"\n单符号模式：分析 {symbol} {timeframe}")
            generate_report(timeframe, symbol_filter=symbol)
        else:
            # 批量模式
            if all_symbols:
                batch_symbols = csv_storage.list_symbols()
                print(f"\n全量模式：分析所有 {len(batch_symbols)} 个 symbol")
            else:
                batch_symbols = TOP_SYMBOLS
                print(f"\n批量模式：分析 TOP_SYMBOLS 配置的 {len(batch_symbols)} 个 symbol")
            
            print(f"\n=== 批量同步 1m 数据 ===")
            for i, sym in enumerate(batch_symbols, 1):
                print(f"[{i}/{len(batch_symbols)}] {sym}...", end=' ')
                if DATA_SOURCE == 'binance':
                    sync_symbol_data(sym)
                else:
                    print("local 源跳过同步")
            
            print(f"\n=== 批量 resample 到 {timeframe} ===")
            for i, sym in enumerate(batch_symbols, 1):
                print(f"[{i}/{len(batch_symbols)}] {sym}...", end=' ')
                ensure_data_exists(sym, timeframe, auto_sync=False)
            
            print(f"\n=== 生成分析报告 ===")
            generate_report(timeframe, batch_symbols=batch_symbols)
    else:
        timeframe = '1h'
        batch_symbols = TOP_SYMBOLS
        
        print(f"\n批量模式：分析 TOP_SYMBOLS 配置的 {len(batch_symbols)} 个 symbol")
        
        print(f"\n=== 批量同步 1m 数据 ===")
        for i, sym in enumerate(batch_symbols, 1):
            print(f"[{i}/{len(batch_symbols)}] {sym}...", end=' ')
            if DATA_SOURCE == 'binance':
                sync_symbol_data(sym)
            else:
                print("local 源跳过同步")
        
        print(f"\n=== 批量 resample 到 {timeframe} ===")
        for i, sym in enumerate(batch_symbols, 1):
            print(f"[{i}/{len(batch_symbols)}] {sym}...", end=' ')
            ensure_data_exists(sym, timeframe, auto_sync=False)
        
        print(f"\n=== 生成分析报告 ===")
        generate_report(timeframe, batch_symbols=batch_symbols)


if __name__ == '__main__':
    main()
