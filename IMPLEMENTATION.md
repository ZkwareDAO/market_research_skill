# Market Researcher 实现总结

## 概述

market_researcher（市场观察员）是一个加密货币市场技术分析 Agent，根据 soul.md 定义实现以下核心功能：

1. **多时间周期数据获取** - 15m, 1h, 4h, 1d OHLCV 数据
2. **技术指标计算** - RSI, MACD, Bollinger Bands, ATR, Volatility, ADX, +DI, -DI
3. **市场趋势判断** - trend_market/ranging_market, bullish/bearish/ranging
4. **Top 10 交易对分析** - 按成交量排序的主流币种
5. **双数据源支持** - local 文件或 Binance API
6. **定时任务调度** - 自动执行数据同步和分析报告
7. **每日文件分割** - 数据按日期分割存储：{symbol}-{timeframe}-{YYYY}-{MM}-{DD}.csv

## 文件结构

```
market_research_skill/
├── SKILL.md                    # Skill 定义文档
├── README.md                   # 使用说明
├── IMPLEMENTATION.md           # 本文件
├── requirements.txt            # Python 依赖
├── .env.sample                 # 环境变量模板
├── scripts/
│   ├── sync_data.py            # 数据同步脚本
│   ├── analyze.py              # 技术分析脚本
│   ├── scheduler.py            # 定时调度脚本
│   ├── csv_storage.py          # CSV 存储管理
│   ├── data_resampler.py       # 数据重采样
│   ├── indicator_calculator.py # 指标计算
│   ├── market_judgment.py      # 市场状态判断
│   └── signal_generator.py     # 信号生成
├── data/                       # 市场数据目录（或配置的外部路径）
│   └── {symbol}/
│       ├── {timeframe}/
│       │   ├── {symbol}-{timeframe}-{YYYY}-{MM}-{DD}.csv
│       │   └── ...
│       └── ...
├── output/                     # 分析报告输出
│   ├── 1h_analysis/
│   ├── 4h_analysis/
│   └── 1d_analysis/
└── logs/                       # 日志目录
```

## 核心技术实现

### 1. CSV 存储管理 (csv_storage.py)

**功能：**
- 按日期分割存储：`{data_path}/{symbol}/{timeframe}/{symbol}-{timeframe}-{YYYY}-{MM}-{DD}.csv`
- 支持增量写入和全量写入
- 加载最近 N 条数据或全部数据
- 按 symbol、timeframe、date 索引

**关键类：**
```python
class CsvStorage:
    def append(symbol, timeframe, df)      # 增量追加
    def save_full(symbol, timeframe, df)   # 全量保存
    def load_recent(symbol, timeframe, limit)  # 加载最近 N 条
    def load_all(symbol, timeframe)        # 加载全部
    def list_symbols()                     # 列出所有交易对
    def list_timeframes(symbol)            # 列出所有周期
    def list_dates(symbol, timeframe)      # 列出所有日期
```

**数据格式：**
```csv
timestamp,open,high,low,close,volume
1713513600000,65000.00,65500.00,64800.00,65200.00,1234.56
```

### 2. 数据同步 (sync_data.py)

**功能：**
- 从 Binance API 或 local 文件同步 OHLCV 数据
- 支持增量同步（只获取新数据）
- 数据缺失告警（local 模式）
- 自动补充数据（Binance 模式）

**关键函数：**
```python
fetch_binance_klines(symbol, interval, start_time, end_time)  # 获取 K 线
sync_symbol_binance(symbol, timeframe)  # Binance 源同步
sync_symbol_local(symbol, timeframe)    # local 源检查
send_wecom_alert(message)               # 发送告警
```

**数据源对比：**

| 特性 | local 源 | Binance 源 |
|------|----------|------------|
| 数据补充 | 告警 | 自动补充 |
| API 依赖 | 无 | 需要网络 |
| 适用场景 | 已有数据管道 | 独立运行 |

### 3. 技术分析 (analyze.py)

**功能：**
- 计算 6+ 种技术指标
- 判断市场趋势
- 生成 Markdown 格式分析报告

**技术指标实现：**

| 指标 | 函数 | 参数 | 说明 |
|------|------|------|------|
| RSI | `calculate_rsi()` | period=14 | 相对强弱指标 |
| MACD | `calculate_macd()` | fast=12, slow=26, signal=9 | 移动平均收敛发散 |
| Bollinger Bands | `calculate_bollinger_bands()` | period=20, std_dev=2 | 布林带 |
| ATR | `calculate_atr()` | period=14 | 平均真实波幅 |
| Volatility | `calculate_volatility()` | period=20 | 波动率 |

**趋势判断逻辑：**
```python
# 单个交易对判断
if rsi_value > 50 and macd_bullish:
    trend = '偏多'
elif rsi_value < 50 and not macd_bullish:
    trend = '偏空'
else:
    trend = '震荡'

# 市场整体判断
if bullish_count > bearish_count * 1.5:
    overall_trend = '趋势市场 - 牛市'
    overall_direction = 'bullish'
```

### 4. 定时调度 (scheduler.py)

**功能：**
- 自动模式：根据当前时间判断执行任务
- 手动模式：指定执行特定分析

**调度逻辑（根据 soul.md）：**
```python
# 每 15 分钟同步数据
if minute % 15 == 0:
    run_sync()

# 每小时整点执行 1h 分析
if minute == 0:
    run_analysis('1h')
    
    # 每 4 小时整点执行 4h 分析
    if hour % 4 == 0:
        run_analysis('4h')
    
    # 每天 0 点执行 1d 分析
    if hour == 0:
        run_analysis('1d')
```

### 5. 模块化组件

#### DataResampler (data_resampler.py)

**功能：**
- 将 1m K 线数据 resample 到 5m/15m/1h/4h/1d
- 自动检测周期边界
- OHLCV 正确聚合（open-first, high-max, low-min, close-last, volume-sum）

**关键方法：**
```python
update_1m(symbol, kline_1m)           # 更新 1m 并 resample
load_from_storage(symbol, timeframe)  # 从 CSV 加载
_save_to_storage(symbol, timeframe)   # 保存到 CSV
```

#### IndicatorCalculator (indicator_calculator.py)

**功能：**
- 使用纯 Python 实现指标计算（无需 TA-Lib 依赖）
- 计算 ADX, +DI, -DI, MACD, RSI

**关键方法：**
```python
calculate(df)              # 计算所有指标
get_latest_values(df)      # 获取最新值
get_latest_adx(df)         # 获取 ADX
get_latest_rsi(df)         # 获取 RSI
get_latest_macd(df)        # 获取 MACD
```

#### MarketJudgment (market_judgment.py)

**功能：**
- 根据多周期指标一致性判断市场状态
- 输出 market_type, direction, confidence

**判断规则：**
- 1d × 4h × 15m 三者方向一致 → trend_market
- 否则 → ranging_market

**关键类：**
```python
@dataclass
class MarketState:
    market_type: str      # trend_market / ranging_market
    direction: str        # bullish / bearish / ranging
    confidence: float     # 0-1
    primary_timeframes: List[str]
    aligned_timeframes: List[str]
    details: Dict

class MarketJudgment:
    judge(indicators_by_timeframe) -> MarketState
    get_summary(state) -> str
```

#### SignalGenerator (signal_generator.py)

**功能：**
- 合并所有周期的指标到一行
- 生成最终的信号 DF

**DF 列结构：**
```
- 基础 OHLCV (来自 1m)
- 各周期指标：adx_1d, adx_4h, adx_1h, adx_15m, ...
- MACD 各周期：macd_1d, macd_signal_1d, macd_hist_1d, ...
- RSI 各周期：rsi_1d, rsi_4h, ...
- 市场状态：market_type, direction, confidence
```

## 配置说明

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATA_SOURCE` | binance | 数据源：local 或 binance |
| `MARKET_RESEARCHER_DATA_PATH` | ./data | 数据保存路径 |
| `BINANCE_API_BASE` | https://api.binance.com | Binance API 地址 |
| `WECOM_WEBHOOK_URL` | - | 企业微信告警 Webhook |
| `TOP_N` | 10 | Top N 交易对数量 |
| `RSI_PERIOD` | 14 | RSI 周期 |
| `MACD_FAST` | 12 | MACD 快线周期 |
| `MACD_SLOW` | 26 | MACD 慢线周期 |
| `MACD_SIGNAL` | 9 | MACD 信号线周期 |
| `BB_PERIOD` | 20 | 布林带周期 |
| `BB_STD` | 2 | 布林带标准差 |
| `ATR_PERIOD` | 14 | ATR 周期 |

### 定时任务配置

**推荐配置（单一入口）：**
```bash
*/15 * * * * cd /path/to/market_research_skill && python scripts/scheduler.py >> logs/scheduler.log 2>&1
```

**分开配置（更灵活）：**
```bash
# 数据同步
*/15 * * * * python scripts/sync_data.py

# 1h 分析
0 * * * * python scripts/analyze.py 1h

# 4h 分析
0 */4 * * * python scripts/analyze.py 4h

# 1d 分析
0 0 * * * python scripts/analyze.py 1d
```

## 输出示例

### 分析报告结构

```markdown
# 市场技术分析 - 1h (2026-04-22 14:00)

## Top 10 交易对

| 排名 | 交易对 | 价格 | 24h 涨跌 | RSI | MACD | 布林带 | ATR | 波动率 | 趋势判断 |
|------|--------|------|---------|-----|------|--------|-----|--------|---------|
| 1 | BTCUSDT | 65200.00 | +1.23% | 55.2 | bullish | 中轨 | 1200.00 | 2.3% | 偏多 |

## 市场整体判断
- 趋势类型：trend_market
- 市场方向：bullish
- 波动率水平：中 (平均 2.50%)
- 多头占比：7/10 (70.0%)
- 空头占比：2/10 (20.0%)

## 详细指标
### RSI 分布
- 超买 (>70): 1 个
- 中性 (30-70): 8 个
- 超卖 (<30): 1 个

### MACD 信号
- 看涨：7 个
- 看跌：3 个
```

### 企业微信告警

```markdown
## 市场数据缺失告警

- 交易对：BTCUSDT
- 时间周期：1h
- 缺失时间：2026-04-22 14:00
- 数据源：local

请检查数据是否已同步到指定目录。
```

## 测试验证

### 已通过测试

✅ 示例数据生成
- 5 个交易对 × 4 个时间周期
- 生成 20 个 CSV 文件
- 数据格式正确

✅ 技术分析
- 1h 分析报告生成
- 4h 分析报告生成
- 1d 分析报告生成
- 指标计算正确
- 趋势判断合理

✅ 报告格式
- Markdown 格式正确
- 表格渲染正常
- 统计信息完整

### 待测试（需网络）

⏳ Binance API 数据同步
⏳ local 数据源集成
⏳ 企业微信告警发送
⏳ 定时任务长期运行

## 依赖项

```
pandas>=2.0.0      # 数据处理
numpy>=1.24.0      # 数值计算
requests>=2.31.0   # HTTP 请求
python-dotenv>=1.0.0  # 环境变量
```

## 已知限制

1. **网络访问** - WSL2 环境默认无法访问外网，需要配置代理
2. **Python 版本** - 需要 Python 3.10+，已测试 Python 3.12
3. **数据源** - local 数据源需要外部同步工具配合
4. **实时性** - 默认每 15 分钟同步一次，非实时数据

## 后续优化

### 功能增强
- [ ] 支持更多技术指标（Stochastic, ADX, etc.）
- [ ] 多周期共振分析
- [ ] 支撑阻力位自动识别
- [ ] K 线形态识别

### 性能优化
- [ ] 数据缓存机制
- [ ] 并行数据获取
- [ ] 增量分析（只分析新数据）

### 集成优化
- [ ] 与企业微信深度集成
- [ ] Obsidian 插件支持
- [ ] Web Dashboard

## 参考资料

- [SKILL.md](./SKILL.md) - 完整 Skill 文档
- [README.md](./README.md) - 快速开始
- soul.md - 市场观察员人格定义
