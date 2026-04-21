---
name: market_researcher
description: 市场观察员 - 获取加密货币市场 OHLCV 数据，计算技术指标，输出市场趋势分析
version: 1.0.0
---

# Market Researcher Skill - 市场观察员

用于获取加密货币市场 OHLCV 数据，计算技术指标，并输出市场趋势性判断。

## 快速开始

**1. 安装依赖**
```bash
cd market_researcher
pip install -r requirements.txt
```

**2. 配置环境变量**
```bash
cp .env.example .env
# 编辑 .env 文件，配置数据源
```

**3. 执行分析**
```bash
# 手动执行分析
python scripts/analyze.py

# 或者使用定时任务
python scripts/scheduler.py
```

## 核心功能

1. **多时间周期数据获取** - 支持 15m, 1h, 4h, 1d OHLCV 数据
2. **技术指标计算** - RSI, MACD, Bollinger Bands, ATR, Volatility 等
3. **市场趋势判断** - 趋势市场/震荡市场，牛市/熊市/震荡
4. **Top 10 交易对分析** - 按成交量排序的主流币种
5. **数据源配置** - 支持 zkware (sync_market_data_skill) 或 Binance API
6. **自动告警** - 数据缺失时发送企业微信告警

## 数据源配置

### 方式一：zkware 数据源

使用 `sync_market_data_skill` 同步的数据，每 15 分钟更新一次。

**环境变量配置：**
```bash
DATA_SOURCE=zkware
MARKET_RESEARCHER_DATA_PATH=/path/to/market_researcher/data
WECOM_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx
```

**特点：**
- 数据由 `sync_market_data_skill` 提供
- 每 15 分钟同步一次
- 数据缺失时发送告警，不自动补充

### 方式二：Binance 数据源

直接调用 Binance API 获取历史 K 线数据。

**环境变量配置：**
```bash
DATA_SOURCE=binance
BINANCE_API_BASE=https://api.binance.com
MARKET_RESEARCHER_DATA_PATH=/path/to/market_researcher/data
WECOM_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx
```

**特点：**
- 每 15 分钟调用 Binance API
- 数据缺失时自动补充
- 无需额外配置 API Key（公开接口）

## 技术指标

### 计算指标列表

| 指标 | 说明 | 时间周期 |
|------|------|---------|
| RSI | 相对强弱指标，判断超买超卖 | 1d, 4h, 1h, 15m, 5m, 1m |
| MACD | 移动平均收敛发散，趋势加速度 | 1d, 4h, 1h, 15m, 5m, 1m |
| Bollinger Bands | 布林带，波动率和趋势 | 1d, 4h, 1h, 15m, 5m, 1m |
| ATR | 平均真实波幅，波动率 | 1d, 4h, 1h, 15m, 5m, 1m |
| Volatility | 波动率 | 1d, 4h, 1h, 15m, 5m, 1m |
| MA | 移动平均线 (MA20, MA50, MA200) | 1d, 4h, 1h, 15m |

### 市场判断逻辑

**趋势市场判断：**
- `trend_market`: 多周期指标一致，趋势明确
- `ranging_market`: 指标分歧，横盘震荡

**市场方向：**
- `bullish`: 牛市，上涨趋势
- `bearish`: 熊市，下跌趋势
- `ranging`: 震荡市

## 定时任务

### 输出频率

| 时间 | 输出内容 |
|------|---------|
| 每小时整点 | Top 10 交易对 1h 技术指标分析 |
| 每 4 小时整点 | Top 10 交易对 4h 技术指标分析 |
| 每天 24:00 | Top 10 交易对 1d 技术指标分析 |

### Crontab 配置

```bash
# 编辑 crontab
crontab -e

# 添加以下配置
*/15 * * * * cd /path/to/market_researcher && python scripts/sync_data.py >> logs/sync.log 2>&1
0 * * * * cd /path/to/market_researcher && python scripts/scheduler.py 1h >> logs/analysis_1h.log 2>&1
0 */4 * * * cd /path/to/market_researcher && python scripts/scheduler.py 4h >> logs/analysis_4h.log 2>&1
0 0 * * * cd /path/to/market_researcher && python scripts/scheduler.py 1d >> logs/analysis_1d.log 2>&1
```

## 输出目录结构

```
market_researcher/
├── data/
│   └── {symbol}/           # 每个交易对一个目录
│       ├── 15m.csv         # 15 分钟 K 线
│       ├── 1h.csv          # 1 小时 K 线
│       ├── 4h.csv          # 4 小时 K 线
│       └── 1d.csv          # 日线 K 线
├── output/
│   ├── 1h_analysis/        # 1 小时分析报告
│   ├── 4h_analysis/        # 4 小时分析报告
│   └── 1d_analysis/        # 日线分析报告
├── logs/                   # 日志目录
├── scripts/
│   ├── sync_data.py        # 数据同步脚本
│   ├── analyze.py          # 技术分析脚本
│   └── scheduler.py        # 定时任务调度
├── .env.example            # 环境变量模板
└── requirements.txt        # Python 依赖
```

## K 线数据格式 (CSV)

```csv
timestamp,open,high,low,close,volume
1713513600000,65000.00,65500.00,64800.00,65200.00,1234.56
```

- `timestamp`: 毫秒时间戳
- `open`: 开盘价
- `high`: 最高价
- `low`: 最低价
- `close`: 收盘价
- `volume`: 成交量

## 分析报告格式

### 1 小时分析报告示例

```markdown
# 市场技术分析 - 1h (2026-04-20 14:00)

## Top 10 交易对

| 排名 | 交易对 | RSI | MACD | BB | ATR | 趋势判断 |
|------|--------|-----|------|----|-----|---------|
| 1 | BTCUSDT | 55.2 |  bullish | 中轨 | 2.3% | 震荡偏多 |
| 2 | ETHUSDT | 62.1 |  bullish | 上轨 | 3.1% | 强势 |
| ... |

## 市场整体判断
- 趋势类型：trend_market
- 市场方向：bullish
- 波动率：中等
```

## 错误处理

### 数据缺失告警

当数据源缺失时，发送企业微信告警：

```json
{
  "msgtype": "markdown",
  "markdown": {
    "content": "## 市场数据缺失告警\n\n- 交易对：BTCUSDT\n- 时间周期：1h\n- 缺失时间：2026-04-20 14:00\n- 数据源：zkware"
  }
}
```

### API 错误处理

- Binance API 失败时自动重试 3 次
- 重试失败后记录日志并继续处理其他交易对
- 不会因单个交易对失败而中断整个流程

## 依赖安装

```bash
cd market_researcher
pip install -r requirements.txt
```

### requirements.txt

```
pandas
numpy
ta-lib
requests
python-dotenv
```

## 命令列表

### /market-sync

同步最新市场数据。

**执行：**
```bash
python scripts/sync_data.py
```

### /market-analyze [interval]

执行技术分析，支持 1h, 4h, 1d。

**执行：**
```bash
python scripts/analyze.py 1h
python scripts/analyze.py 4h
python scripts/analyze.py 1d
```

### /market-top10 [interval]

获取 Top 10 交易对的技术分析。

**执行：**
```bash
python scripts/scheduler.py 1h
```

## 配置说明

### 环境变量

在 skill 目录创建 `.env` 文件：

```bash
cp .env.example .env
```

**必需配置：**
```bash
# 数据源：zkware 或 binance
DATA_SOURCE=binance

# 数据保存路径
MARKET_RESEARCHER_DATA_PATH=/home/caiqingfeng/.openclaw/workspace/market_researcher/data

# 企业微信告警 Webhook（可选）
WECOM_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx
```

**可选配置：**
```bash
# Binance API 配置
BINANCE_API_BASE=https://api.binance.com

# Top N 交易对数量（默认 10）
TOP_N=10

# 技术指标参数
RSI_PERIOD=14
MACD_FAST=12
MACD_SLOW=26
MACD_SIGNAL=9
BB_PERIOD=20
BB_STD=2
ATR_PERIOD=14
```

## 示例用法

### 手动同步数据
```bash
python scripts/sync_data.py
```

### 执行 1 小时分析
```bash
python scripts/scheduler.py 1h
```

### 执行 4 小时分析
```bash
python scripts/scheduler.py 4h
```

### 执行日线分析
```bash
python scripts/scheduler.py 1d
```

## 注意事项

1. **数据源选择** - zkware 数据源需要确保 `sync_market_data_skill` 正常运行
2. **API 限流** - Binance 公开接口有速率限制，避免过于频繁的请求
3. **时间同步** - 确保系统时间准确，定时任务基于整点执行
4. **数据存储** - K 线数据按交易对和时间周期分别存储，便于回溯
5. **告警配置** - 建议配置企业微信告警，及时发现数据缺失问题

## 参考资料

- `soul.md.md` - 市场观察员人格定义
- `scripts/sync_data.py` - 数据同步实现
- `scripts/analyze.py` - 技术分析实现
- `scripts/scheduler.py` - 定时任务调度
