---
name: market-research
description: >
  加密货币市场技术分析与 Deribit 期权数据快照。
  当用户需要获取加密货币（BTC、ETH、SOL、XRP 等）技术指标分析（RSI、MACD、ADX、布林带、ATR 等）、
  市场趋势判断（趋势/震荡、牛市/熊市）时触发。
  当用户需要获取 Deribit BTC/ETH 期权 ATM 价格与隐含波动率（IV）、25-Delta Call/Put IV 时触发。
  当用户说"市场分析"、"技术指标"、"期权信息"、"期权快照"、"IV"、"波动率"、"趋势判断"时触发。
---

# Market Researcher Skill - 市场观察员

获取加密货币市场 OHLCV 数据，计算技术指标，输出市场趋势判断；获取 Deribit BTC/ETH 期权 ATM 价格/IV 及 25-Delta IV。

## Capabilities

1. **多币种技术指标分析** - 支持 BTC、ETH、SOL、XRP、DOGE 等任意 Binance 上市代币的 RSI、MACD、Bollinger Bands、ATR、Volatility、ADX、+DI/-DI 计算
2. **多时间周期** - 支持 15m、1h、4h、1d OHLCV 数据获取与分析
3. **市场趋势判断** - 基于多周期指标一致性判断趋势市场/震荡市场、bullish/bearish/ranging
4. **Top N 交易对分析** - 批量分析配置的主流币种
5. **双数据源** - 支持 local（rsync 远程同步）或 Binance API
6. **数据缺失告警** - local 源数据缺失时发送企业微信告警
7. **Deribit 期权快照** - 获取 BTC/ETH 本周五、下周五、月底到期的 ATM 期权价格/IV 及 25-Delta Call/Put IV

## How to Use

### 技术指标分析

```bash
# 安装依赖
cd market_research_skill && pip install -r requirements.txt

# 配置环境变量
cp .env.sample .env  # 编辑 .env 配置数据源

# 单币种分析
python scripts/analyze_enhanced.py 1h BTCUSDT

# 批量分析 Top N 币种
python scripts/analyze_enhanced.py 1h
python scripts/analyze_enhanced.py 4h
python scripts/analyze_enhanced.py 1d

# 数据同步
python scripts/sync_data.py              # 同步所有
python scripts/sync_data.py BTCUSDT      # 同步单个

# 定时调度
python scripts/scheduler.py              # 自动模式
python scripts/scheduler.py 1h           # 指定周期
python scripts/scheduler.py sync         # 仅同步
```

### Deribit 期权快照

```bash
python scripts/deribit_options.py
# 或
bash scripts/run_options_snapshot.sh
```

## Output Format

### 技术分析报告

保存到 `output/{symbol}/{timeframe}_analysis/` 或 `output/all/{timeframe}_analysis/`，Markdown 格式：

| 字段 | 说明 |
|------|------|
| 交易对 | 币种名称 |
| 价格 / 24h 涨跌 | 最新价和变化率 |
| RSI | 相对强弱指标 (超买>70 / 超卖<30) |
| MACD | bullish / bearish |
| ADX | 趋势强度 (≥25 趋势市场) |
| 布林带位置 | 上轨外/上轨侧/下轨侧/下轨外 |
| ATR / 波动率 | 平均真实波幅和年化波动率 |
| 运行方向 / 价格趋势 | bullish/bearish + 趋势市场/震荡市场 |

### 期权快照报告

保存到 `output/options_snapshot/snapshot_{YYYY-MM-DD_HH-MM}.md`，包含：

| 报告区域 | 包含字段 |
|----------|---------|
| ATM 期权（BTC/ETH 分表） | 到期日、行权价、Call/Put 价格、Call/Put IV |
| 25-Delta IV（BTC/ETH 分表） | 到期日、25D Call/Put IV 及 Strike、Risk Reversal (Call IV − Put IV) |
| 关键观察 | IV 水平对比、Put/Call 偏斜、Risk Reversal 方向、期限结构形态、隐含方向 |

## Example Usage

用户输入示例及预期行为：

| 用户输入 | 执行动作 |
|----------|---------|
| "分析下 BTC 1小时技术指标" | `python scripts/analyze_enhanced.py 1h BTCUSDT` |
| "SOL 4小时分析" | `python scripts/analyze_enhanced.py 4h SOLUSDT` |
| "跑一下所有币种日线分析" | `python scripts/analyze_enhanced.py 1d` |
| "期权信息" / "期权快照" / "IV 数据" | `python scripts/deribit_options.py` |
| "同步数据" | `python scripts/sync_data.py` |

## Scripts

| 脚本 | 功能 |
|------|------|
| `scripts/sync_data.py` | 从 Binance API 或远程 rsync 同步 OHLCV 1m 数据 |
| `scripts/analyze_enhanced.py` | 计算技术指标并生成 Markdown 分析报告，支持单币种或批量模式 |
| `scripts/scheduler.py` | 定时任务调度，根据当前时间自动执行同步和对应周期的分析 |
| `scripts/csv_storage.py` | CSV 存储管理，按日期分割文件的读写（`{symbol}-{timeframe}-{YYYY}-{MM}-{DD}.csv`） |
| `scripts/data_resampler.py` | 将 1m K 线数据 resample 到 5m/15m/1h/4h/1d 多周期 |
| `scripts/indicator_calculator.py` | 纯 Python 实现 ADX、+DI/-DI、MACD、RSI 等指标计算 |
| `scripts/market_judgment.py` | 基于多周期指标一致性判断市场类型（trend/ranging）和方向（bullish/bearish） |
| `scripts/signal_generator.py` | 合并所有周期指标到一行，生成最终信号 DataFrame |
| `scripts/deribit_options.py` | 查询 Deribit 公开 API，获取 BTC/ETH ATM 期权价格/IV 和 25-Delta IV |
| `scripts/run_options_snapshot.sh` | 期权快照的 shell 包装脚本，适合 crontab 调用 |
| `scripts/sync_remote_data.sh` | 从远程服务器 rsync 数据的 shell 脚本 |
| `scripts/cron-sync.sh` | 数据同步 crontab 入口脚本 |

## Configuration

在 skill 目录创建 `.env` 文件（`cp .env.sample .env`）：

### 数据源配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATA_SOURCE` | `binance` | 数据源：`local`（rsync）或 `binance`（API） |
| `MARKET_RESEARCHER_DATA_PATH` | `./data` | 数据保存路径 |
| `BINANCE_API_BASE` | `https://api.binance.com` | Binance API 地址 |
| `TOP_SYMBOLS` | 内置默认列表 | 逗号分隔的交易对列表，如 `BTCUSDT,ETHUSDT,SOLUSDT` |
| `TOP_N` | `10` | Top N 交易对数量 |
| `OUTPUT_PATH` | `./output` | 报告输出目录 |

### 技术指标参数

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `RSI_PERIOD` | `14` | RSI 周期 |
| `MACD_FAST` / `MACD_SLOW` / `MACD_SIGNAL` | `12` / `26` / `9` | MACD 参数 |
| `BB_PERIOD` / `BB_STD` | `20` / `2` | 布林带参数 |
| `ATR_PERIOD` | `14` | ATR 周期 |

### Deribit 期权配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DERIBIT_API_BASE` | `https://www.deribit.com/api/v2` | Deribit API 地址 |
| `HTTPS_PROXY` | （空） | HTTP/HTTPS 代理地址，如 `http://192.168.1.201:10809` |

### 告警配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `WECOM_WEBHOOK_URL` | （空） | 企业微信告警 Webhook URL |

## Deribit 期权快照

### API 调用流程

1. `GET /public/get_instruments` — 获取所有活跃期权合约，按 `expiration_timestamp` 过滤目标到期日
2. `GET /public/get_book_summary_by_currency` — 批量获取 `mark_iv`、`mark_price`、`underlying_price`，确定 ATM 行权价
3. `GET /public/ticker` — 逐个获取 `greeks.delta`，找到 delta 最接近 0.25（call）和 -0.25（put）的期权

### 到期日匹配规则

- 本周五：当前周的周五；若当天为周五且已过 08:00 UTC，则取下周五
- 下周五：本周五的下一个周五
- 月底：当月最后一天
- 若 Deribit 无对应到期合约，自动匹配 ±3 天内最近的可用到期日

## Limitations

1. **技术分析数据源** — local 数据源需确保外部同步工具正常运行
2. **API 限流** — Binance 公开接口有速率限制，避免过于频繁请求
3. **时间同步** — 定时任务基于整点执行，需确保系统时间准确
4. **期权币种** — Deribit 期权快照目前仅支持 BTC 和 ETH
5. **网络代理** — Deribit API 访问可能需要配置 `HTTPS_PROXY`

## References

- `references/IMPLEMENTATION.md` — 详细的模块实现说明、类定义、函数签名
- `scripts/` — 所有可执行脚本（见 Scripts 章节）
- [Deribit API v2 文档](https://docs.deribit.com/) — 期权公开 API 参考
