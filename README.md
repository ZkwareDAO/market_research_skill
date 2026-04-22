# Market Researcher Skill - 市场观察员

加密货币市场技术分析工具，获取 OHLCV 数据并计算技术指标，输出市场趋势判断。

## 快速开始

### 1. 安装依赖

```bash
cd market_research_skill
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.sample .env
# 编辑 .env 文件
```

**最小配置：**
```bash
DATA_SOURCE=binance  # 或 local
MARKET_RESEARCHER_DATA_PATH=D:/workspace/shared_data/binance/futures/um/daily/data
```

### 3. 运行

```bash
# 同步最新数据
python scripts/sync_data.py

# 执行技术分析
python scripts/analyze.py 1h  # 1 小时分析
python scripts/analyze.py 4h  # 4 小时分析
python scripts/analyze.py 1d  # 日线分析

# 定时调度（自动模式）
python scripts/scheduler.py
```

## 功能特性

- ✅ 多时间周期支持：15m, 1h, 4h, 1d
- ✅ 技术指标：RSI, MACD, Bollinger Bands, ATR, Volatility, ADX, +DI, -DI
- ✅ 市场趋势判断：trend_market/ranging_market, bullish/bearish/ranging
- ✅ Top 10 交易对自动分析
- ✅ 双数据源：Binance API / local 文件
- ✅ 数据缺失告警（企业微信）
- ✅ 每日文件分割：{symbol}-{timeframe}-{YYYY}-{MM}-{DD}.csv

## 目录结构

```
market_research_skill/
├── SKILL.md                # 完整 Skill 文档
├── README.md               # 本文件
├── .env.sample             # 环境变量模板
├── requirements.txt        # Python 依赖
├── scripts/
│   ├── sync_data.py        # 数据同步
│   ├── analyze.py          # 技术分析
│   ├── scheduler.py        # 定时调度
│   ├── csv_storage.py      # CSV 存储管理
│   ├── data_resampler.py   # 数据重采样
│   ├── indicator_calculator.py  # 指标计算
│   ├── market_judgment.py  # 市场状态判断
│   └── signal_generator.py # 信号生成
├── logs/                   # 日志目录
└── output/                 # 分析报告输出
```

## 定时任务配置

```bash
# 编辑 crontab
crontab -e

# 添加以下配置（单一入口）
*/15 * * * * cd /path/to/market_research_skill && python scripts/scheduler.py >> logs/scheduler.log 2>&1
```

## 输出示例

分析报告会输出到 `output/{timeframe}_analysis/` 目录，包含：
- Top 10 交易对技术指标表格
- 市场整体趋势判断
- RSI/MACD 分布统计

详见 [SKILL.md](./SKILL.md) 完整文档。

## 数据格式

数据存储格式（按日期分割）：
```
{data_path}/{symbol}/{timeframe}/{symbol}-{timeframe}-{YYYY}-{MM}-{DD}.csv
```

K 线数据格式：
```csv
timestamp,open,high,low,close,volume
1713513600000,65000.00,65500.00,64800.00,65200.00,1234.56
```

## 模块化架构

| 模块 | 功能 |
|------|------|
| CsvStorage | CSV 存储管理，按日期分割读写 |
| DataResampler | 数据重采样，1m → 5m/15m/1h/4h/1d |
| IndicatorCalculator | 指标计算（ADX, MACD, RSI） |
| MarketJudgment | 市场状态判断（趋势/震荡） |
| SignalGenerator | 信号 DF 生成，合并多周期指标 |

## 参考资料

- [SKILL.md](./SKILL.md) - 完整 Skill 文档
- soul.md - 市场观察员人格定义
