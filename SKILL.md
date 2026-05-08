# Market Researcher Skill - 市场观察员

用于获取加密货币市场 OHLCV 数据，计算技术指标，并输出市场趋势性判断。

## 快速开始

**1. 安装依赖**
```bash
cd market_research_skill
pip install -r requirements.txt
```

**2. 配置环境变量**
```bash
cp .env.sample .env
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
2. **技术指标计算** - RSI, MACD, Bollinger Bands, ATR, Volatility, ADX, +DI, -DI
3. **市场趋势判断** - 趋势市场/震荡市场，牛市/熊市/震荡
4. **Top 10 交易对分析** - 按成交量排序的主流币种
5. **数据源配置** - 支持 local (本地文件) 或 Binance API
6. **自动告警** - 数据缺失时发送企业微信告警 (local 源)
7. **每日文件分割** - 数据按日期分割存储，便于管理和回溯
8. **Deribit 期权快照** - BTC/ETH ATM 期权价格/IV 及 25-Delta IV（本周五、下周五、月底到期）

## 数据源配置

### 方式一：local 数据源（推荐）

使用 `scripts/sync_remote_data.sh` 从远程服务器 rsync 数据。

**环境变量配置：**
```bash
DATA_SOURCE=local
MARKET_RESEARCHER_DATA_PATH=/home/zkware/workspace/shared_data
WECOM_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx
```

**远程同步脚本：**
```bash
# 手动执行远程同步
bash scripts/sync_remote_data.sh

# 或从 Python 自动调用（DATA_SOURCE=local 时自动执行）
python scripts/sync_data.py
```

**远程服务器配置（在 sync_remote_data.sh 中修改）：**
```bash
REMOTE_USER="zkware"
REMOTE_HOST="192.168.1.10"
REMOTE_PATH="~/workspace/go_projects/trading_crypto_bot/data"
LOCAL_PATH="/home/zkware/workspace/shared_data"
```

**特点：**
- 数据按日期分割存储：`{data_path}/{symbol}/{timeframe}/{symbol}-{timeframe}-{YYYY}-{MM}-{DD}.csv`
- 数据缺失时发送告警，不自动补充
- 适合与外部数据同步工具配合使用

### 方式二：Binance 数据源

直接调用 Binance API 获取历史 K 线数据。

**环境变量配置：**
```bash
DATA_SOURCE=binance
BINANCE_API_BASE=https://api.binance.com
MARKET_RESEARCHER_DATA_PATH=D:/workspace/shared_data/binance/futures/um/daily/data
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
| ADX | 平均趋向指标，趋势强度 | 1d, 4h, 1h, 15m, 5m, 1m |
| +DI / -DI | 趋向指标，方向判断 | 1d, 4h, 1h, 15m, 5m, 1m |

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

根据 soul.md 定义：

| 时间 | 输出内容 |
|------|---------|
| 每小时整点 | Top 10 交易对 1h 技术指标分析 |
| 每 4 小时整点 | Top 10 交易对 4h 技术指标分析 |
| 每天 24:00 | Top 10 交易对 1d 技术指标分析 |

### Crontab 配置

```bash
# 编辑 crontab
crontab -e

# 添加以下配置（单一入口推荐）
*/15 * * * * cd /path/to/market_research_skill && python scripts/scheduler.py >> logs/scheduler.log 2>&1
```

或者分开配置：

```bash
# 数据同步（每 15 分钟）
*/15 * * * * python scripts/sync_data.py

# 1h 分析（每小时整点）
0 * * * * python scripts/analyze.py 1h

# 4h 分析（每 4 小时整点）
0 */4 * * * python scripts/analyze.py 4h

# 1d 分析（每天 0 点）
0 0 * * * python scripts/analyze.py 1d
```

## 输出目录结构

```
market_research_skill/
├── data/ 或 workspace/shared_data/binance/futures/um/daily/data/
│   └── {symbol}/           # 每个交易对一个目录
│       ├── 1h/             # 时间周期目录
│       │   ├── {symbol}-1h-2026-04-21.csv  # 每日文件
│       │   └── {symbol}-1h-2026-04-22.csv
│       ├── 4h/
│       └── 1d/
├── output/
│   ├── 1h_analysis/        # 1 小时分析报告
│   ├── 4h_analysis/        # 4 小时分析报告
│   ├── 1d_analysis/        # 日线分析报告
│   └── options_snapshot/   # Deribit 期权快照报告
├── logs/                   # 日志目录
├── scripts/
│   ├── sync_data.py        # 数据同步
│   ├── analyze.py          # 技术分析
│   ├── scheduler.py        # 定时任务调度
│   ├── csv_storage.py      # CSV 存储管理
│   ├── data_resampler.py   # 数据重采样
│   ├── indicator_calculator.py  # 指标计算
│   ├── market_judgment.py  # 市场状态判断
│   ├── signal_generator.py # 信号生成
│   └── deribit_options.py  # Deribit 期权快照
├── .env.sample             # 环境变量模板
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
# 市场技术分析 - 1h (2026-04-22 14:00)

## Top 10 交易对

| 排名 | 交易对 | 价格 | 24h 涨跌 | RSI | MACD | 布林带 | ATR | 波动率 | 趋势判断 |
|------|--------|------|---------|-----|------|--------|-----|--------|---------|
| 1 | BTCUSDT | 65200.00 | +1.23% | 55.2 | bullish | 中轨 | 2.3% | 偏多 |
| 2 | ETHUSDT | 3500.00 | +2.15% | 62.1 | bullish | 上轨 | 3.1% | 强势 |
| ... |

## 市场整体判断
- 趋势类型：trend_market
- 市场方向：bullish
- 波动率：中等
```

## 错误处理

### 数据缺失告警

当数据源缺失时（local 模式），发送企业微信告警：

```markdown
## 市场数据缺失告警

- 交易对：BTCUSDT
- 时间周期：1h
- 缺失时间：2026-04-22 14:00
- 数据源：local

请检查数据是否已同步到指定目录。
```

### API 错误处理

- Binance API 失败时自动重试 3 次
- 重试失败后记录日志并继续处理其他交易对
- 不会因单个交易对失败而中断整个流程

## 依赖安装

```bash
cd market_research_skill
pip install -r requirements.txt
```

### requirements.txt

```
pandas>=2.0.0
numpy>=1.24.0
requests>=2.31.0
python-dotenv>=1.0.0
```

## 命令列表

### 同步数据

```bash
python scripts/sync_data.py
```

### 执行技术分析

```bash
python scripts/analyze_enhanced.py 1h BTCUSDT  # 1 小时分析 BTCUSDT
python scripts/analyze_enhanced.py 4h   # 4 小时分析 top 交易币对
python scripts/analyze_enhanced.py 1d   # 日线分析 top 交易币对
```

### 定时调度

```bash
python scripts/scheduler.py      # 自动模式
python scripts/scheduler.py 1h   # 指定 1h 分析
python scripts/scheduler.py sync # 仅同步数据
```

### Deribit 期权快照

```bash
python scripts/deribit_options.py  # 获取 BTC/ETH ATM 期权及 25-Delta IV
```

## 配置说明

### 环境变量

在 skill 目录创建 `.env` 文件：

```bash
cp .env.sample .env
```

**必需配置：**
```bash
# 数据源：local 或 binance
DATA_SOURCE=binance

# 数据保存路径
MARKET_RESEARCHER_DATA_PATH=D:/workspace/shared_data/binance/futures/um/daily/data

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

# Deribit 期权快照配置
DERIBIT_API_BASE=https://www.deribit.com/api/v2
HTTPS_PROXY=http://192.168.1.201:10809
```

## 模块化组件

### CsvStorage
CSV 存储管理，支持按日期分割的文件读写。

### DataResampler
数据重采样，将 1m K 线数据 resample 到 5m/15m/1h/4h/1d 多周期。

### IndicatorCalculator
指标计算，支持 TA-Lib 或纯 Python 实现计算 ADX、MACD、RSI 等指标。

### MarketJudgment
市场状态判断，根据多周期指标一致性判断市场类型和方向。

### SignalGenerator
信号生成，合并所有周期的指标到一行，生成最终的信号 DF。

## Deribit 期权快照

从 Deribit 交易所获取 BTC/ETH 期权市场数据，生成期权快照报告。

### 功能

1. **ATM 期权价格与 IV** — 获取行权价最接近现货价格的期权的 mark_price 和 mark_iv
2. **25-Delta Call/Put IV** — 获取 delta 最接近 ±0.25 的期权的 mark_iv，并计算 Risk Reversal
3. **三个到期日** — 本周五、下周五、当月月底（Deribit 期权在到期日 08:00 UTC 结算）

### 数据源

- **API**：Deribit 公开 API（`https://www.deribit.com/api/v2`），无需认证
- **代理**：通过 `HTTPS_PROXY` 环境变量配置 HTTP 代理

### API 调用流程

1. `GET /public/get_instruments` — 获取所有活跃期权合约，按 `expiration_timestamp` 过滤目标到期日
2. `GET /public/get_book_summary_by_currency` — 批量获取所有期权的 `mark_iv`、`mark_price`、`underlying_price`，用于确定 ATM 行权价
3. `GET /public/ticker` — 逐个获取目标到期日合约的 `greeks.delta`，找到 delta 最接近 0.25（call）和 -0.25（put）的期权

### 到期日匹配规则

- 本周五：当前周的周五；若当天为周五且已过 08:00 UTC，则取下周五
- 下周五：本周五的下一个周五
- 月底：当月最后一天
- 若目标日期在 Deribit 无对应到期合约，自动匹配 ±3 天内最近的可用到期日

### 执行命令

```bash
python scripts/deribit_options.py
```

### 输出

- 终端打印完整报告
- 保存 Markdown 文件到 `output/options_snapshot/snapshot_{YYYY-MM-DD_HH-MM}.md`

### 报告内容

| 报告区域 | 包含字段 |
|----------|---------|
| ATM 期权（按币种分表） | 到期日、行权价、Call 价格、Put 价格、Call IV、Put IV |
| 25-Delta IV（按币种分表） | 到期日、25D Call IV、25D Call Strike、25D Put IV、25D Put Strike、Risk Reversal (Call IV − Put IV) |

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DERIBIT_API_BASE` | `https://www.deribit.com/api/v2` | Deribit API 地址 |
| `HTTPS_PROXY` | （空） | HTTP/HTTPS 代理地址，如 `http://192.168.1.201:10809` |
| `OUTPUT_PATH` | `./output` | 报告输出目录（与技术分析报告共用） |

## 注意事项

1. **数据源选择** - local 数据源需要确保外部数据同步工具正常运行
2. **API 限流** - Binance 公开接口有速率限制，避免过于频繁的请求
3. **时间同步** - 确保系统时间准确，定时任务基于整点执行
4. **数据存储** - K 线数据按交易对、时间周期、日期分别存储，便于回溯
5. **告警配置** - 建议配置企业微信告警，及时发现数据缺失问题

## 参考资料

- soul.md - 市场观察员人格定义
- scripts/csv_storage.py - CSV 存储管理实现
- scripts/data_resampler.py - 数据重采样实现
- scripts/indicator_calculator.py - 指标计算实现
- scripts/market_judgment.py - 市场状态判断实现
- scripts/signal_generator.py - 信号生成实现
- scripts/deribit_options.py - Deribit 期权快照实现
- [Deribit API v2 文档](https://docs.deribit.com/) - 期权公开 API 参考
