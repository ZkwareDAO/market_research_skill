# Market Researcher 实现总结

## 概述

market_researcher（市场观察员）是一个加密货币市场技术分析 Agent，实现了以下核心功能：

1. **多时间周期数据获取** - 15m, 1h, 4h, 1d OHLCV 数据
2. **技术指标计算** - RSI, MACD, Bollinger Bands, ATR, Volatility
3. **市场趋势判断** - trend_market/ranging_market, bullish/bearish/ranging
4. **Top 10 交易对分析** - 按成交量排序的主流币种
5. **双数据源支持** - Binance API 或 zkware
6. **定时任务调度** - 自动执行数据同步和分析报告

## 文件结构

```
market_researcher/
├── SKILL.md                    # Skill 定义文档（7.9KB）
├── README.md                   # 使用说明（2.0KB）
├── EXAMPLES.md                 # 使用示例（3.4KB）
├── IMPLEMENTATION.md           # 实现总结（本文件）
├── requirements.txt            # Python 依赖
├── .env.example                # 环境变量模板
├── scripts/
│   ├── sync_data.py            # 数据同步脚本（8.2KB）
│   ├── analyze.py              # 技术分析脚本（9.3KB）
│   ├── scheduler.py            # 定时调度脚本（3.2KB）
│   └── generate_sample_data.py # 示例数据生成（3.0KB）
├── data/                       # 市场数据目录
│   └── {symbol}/
│       ├── 15m.csv
│       ├── 1h.csv
│       ├── 4h.csv
│       └── 1d.csv
├── output/                     # 分析报告输出
│   ├── 1h_analysis/
│   ├── 4h_analysis/
│   └── 1d_analysis/
└── logs/                       # 日志目录
```

## 核心技术实现

### 1. 数据同步 (sync_data.py)

**功能：**
- 从 Binance API 或 zkware 同步 OHLCV 数据
- 支持增量同步（只获取新数据）
- 数据缺失告警（zkware 模式）
- 自动补充数据（Binance 模式）

**关键函数：**
```python
fetch_binance_klines(symbol, interval, start_time, end_time)  # 获取 K 线
load_existing_data(symbol, timeframe)                          # 加载已有数据
save_data(symbol, timeframe, df)                               # 保存数据
send_wecom_alert(message)                                      # 发送告警
```

**数据格式：**
```csv
timestamp,open,high,low,close,volume
1713513600000,65000.00,65500.00,64800.00,65200.00,1234.56
```

### 2. 技术分析 (analyze.py)

**功能：**
- 计算 6 种技术指标
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
# 趋势判断
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

### 3. 定时调度 (scheduler.py)

**功能：**
- 自动模式：根据当前时间判断执行任务
- 手动模式：指定执行特定分析

**调度逻辑：**
```python
# 每 15 分钟同步数据
if minute % 15 == 0:
    run_sync()

# 每小时整点执行 1h 分析
if minute == 0:
    run_analysis('1h')
    if hour % 4 == 0:
        run_analysis('4h')
    if hour == 0:
        run_analysis('1d')
```

### 4. 示例数据生成 (generate_sample_data.py)

**功能：**
- 生成模拟 OHLCV 数据
- 使用随机游走模型
- 可重复的随机性（基于 symbol 的 hash）

**用途：**
- 离线测试
- 开发调试
- 演示展示

## 配置说明

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATA_SOURCE` | binance | 数据源：binance 或 zkware |
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
*/15 * * * * cd /path/to/market_researcher && python3 scripts/scheduler.py >> logs/scheduler.log 2>&1
```

**分开配置（更灵活）：**
```bash
# 数据同步
*/15 * * * * python3 scripts/sync_data.py

# 1h 分析
0 * * * * python3 scripts/analyze.py 1h

# 4h 分析
0 */4 * * * python3 scripts/analyze.py 4h

# 1d 分析
0 0 * * * python3 scripts/analyze.py 1d
```

## 输出示例

### 分析报告结构

```markdown
# 市场技术分析 - 1h (2026-04-20 14:00)

## Top 10 交易对
[技术指标表格]

## 市场整体判断
- 趋势类型：trend_market/ranging_market
- 市场方向：bullish/bearish/ranging
- 波动率水平：高/中/低
- 多头占比：X/Y (Z%)
- 空头占比：X/Y (Z%)

## 详细指标
### RSI 分布
### MACD 信号
```

### 企业微信告警

```markdown
## 市场数据缺失告警

- 交易对：BTCUSDT
- 时间周期：1h
- 缺失时间：2026-04-20 14:00
- 数据源：zkware
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
⏳ zkware 数据源集成
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
3. **数据源** - zkware 数据源需要 `sync_market_data_skill` 配合
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
- [EXAMPLES.md](./EXAMPLES.md) - 使用示例
- [README.md](./README.md) - 快速开始
- [soul.md.md](../../../team_docs/技术空间/projects/CryptoAgent/核心体验/market_researcher/soul.md.md) - 原始需求定义
