# Market Researcher Skill - 市场观察员

加密货币市场技术分析工具，获取 OHLCV 数据并计算技术指标，输出市场趋势判断。

## 快速开始

### 1. 安装依赖

```bash
cd ~/.openclaw/workspace/skills/market_researcher
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件
```

**最小配置：**
```bash
DATA_SOURCE=binance  # 或 zkware
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
- ✅ 技术指标：RSI, MACD, Bollinger Bands, ATR, Volatility
- ✅ 市场趋势判断：trend_market/ranging_market, bullish/bearish/ranging
- ✅ Top 10 交易对自动分析
- ✅ 双数据源：Binance API / zkware
- ✅ 数据缺失告警（企业微信）

## 目录结构

```
market_researcher/
├── SKILL.md              # Skill 定义文档
├── README.md             # 使用说明
├── requirements.txt      # Python 依赖
├── .env.example          # 环境变量模板
├── scripts/
│   ├── sync_data.py      # 数据同步
│   ├── analyze.py        # 技术分析
│   └── scheduler.py      # 定时调度
├── logs/                 # 日志目录
└── output/               # 分析报告输出
```

## 定时任务配置

```bash
# 编辑 crontab
crontab -e

# 添加以下配置
*/15 * * * * cd ~/.openclaw/workspace/skills/market_researcher && python scripts/scheduler.py >> logs/scheduler.log 2>&1
```

## 输出示例

分析报告会输出到 `output/{timeframe}_analysis/` 目录，包含：
- Top 10 交易对技术指标表格
- 市场整体趋势判断
- RSI/MACD 分布统计

详见 [SKILL.md](./SKILL.md) 完整文档。
