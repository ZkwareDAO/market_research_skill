# Market Researcher 使用示例

## 快速测试

### 1. 生成示例数据（离线测试）

```bash
cd ~/.openclaw/workspace/skills/market_researcher
python3 scripts/generate_sample_data.py
```

### 2. 执行技术分析

```bash
# 1 小时分析
python3 scripts/analyze.py 1h

# 4 小时分析
python3 scripts/analyze.py 4h

# 日线分析
python3 scripts/analyze.py 1d
```

### 3. 查看报告

```bash
# 查看最新的 1h 分析报告
ls -lt output/1h_analysis/ | head -5
cat output/1h_analysis/analysis_*.md | tail -50
```

## 真实数据源配置

### 使用 Binance API

1. 编辑 `.env` 文件：
```bash
DATA_SOURCE=binance
BINANCE_API_BASE=https://api.binance.com
```

2. 同步数据：
```bash
python3 scripts/sync_data.py
```

3. 执行分析：
```bash
python3 scripts/analyze.py 1h
```

### 使用 zkware 数据源

1. 编辑 `.env` 文件：
```bash
DATA_SOURCE=zkware
MARKET_RESEARCHER_DATA_PATH=/path/to/your/data
WECOM_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx
```

2. 确保 `sync_market_data_skill` 正常运行

3. 执行分析：
```bash
python3 scripts/analyze.py 1h
```

## 定时任务配置

### 方法一：使用 scheduler.py

```bash
# 编辑 crontab
crontab -e

# 添加以下配置
*/15 * * * * cd ~/.openclaw/workspace/skills/market_researcher && python3 scripts/scheduler.py >> logs/scheduler.log 2>&1
```

scheduler.py 会自动判断时间并执行相应的分析：
- 每 15 分钟：同步数据
- 每小时整点：1h 分析
- 每 4 小时整点：4h 分析
- 每天 0 点：1d 分析

### 方法二：分开配置

```bash
# 数据同步（每 15 分钟）
*/15 * * * * cd ~/.openclaw/workspace/skills/market_researcher && python3 scripts/sync_data.py >> logs/sync.log 2>&1

# 1h 分析（每小时整点）
0 * * * * python3 ~/.openclaw/workspace/skills/market_researcher/scripts/analyze.py 1h >> logs/analysis_1h.log 2>&1

# 4h 分析（每 4 小时）
0 */4 * * * python3 ~/.openclaw/workspace/skills/market_researcher/scripts/analyze.py 4h >> logs/analysis_4h.log 2>&1

# 1d 分析（每天 0 点）
0 0 * * * python3 ~/.openclaw/workspace/skills/market_researcher/scripts/analyze.py 1d >> logs/analysis_1d.log 2>&1
```

## 输出示例

### 1 小时分析报告

```markdown
# 市场技术分析 - 1h (2026-04-20 14:00)

## Top 10 交易对

| 排名 | 交易对 | 价格 | 24h 涨跌 | RSI | MACD | 布林带 | ATR | 波动率 | 趋势判断 |
|------|--------|------|---------|-----|------|--------|-----|--------|---------|
| 1 | BTCUSDT | 65200.00 | +1.23% | 55.2 | bullish | 中轨 | 1200.00 | 2.3% | 偏多 |
| 2 | ETHUSDT | 3500.00 | +2.15% | 62.1 | bullish | 上轨 | 80.00 | 3.1% | 强势 |
| ... |

## 市场整体判断
- 趋势类型：trend_market
- 市场方向：bullish
- 波动率：中等
```

## 自定义配置

### 修改 Top N 数量

编辑 `.env`：
```bash
TOP_N=20  # 分析前 20 个交易对
```

### 修改技术指标参数

编辑 `.env`：
```bash
RSI_PERIOD=14      # RSI 周期
MACD_FAST=12       # MACD 快线
MACD_SLOW=26       # MACD 慢线
MACD_SIGNAL=9      # MACD 信号线
BB_PERIOD=20       # 布林带周期
BB_STD=2           # 布林带标准差
ATR_PERIOD=14      # ATR 周期
```

## 故障排查

### 数据缺失

检查数据文件是否存在：
```bash
ls -lh data/BTCUSDT/
```

如果文件不存在，运行：
```bash
python3 scripts/sync_data.py
```

### 分析失败

查看日志：
```bash
tail -50 logs/analysis_1h.log
```

手动执行分析看错误信息：
```bash
python3 scripts/analyze.py 1h
```

### 网络连接问题

如果使用 Binance API 但网络不可达：
1. 检查网络连接
2. 配置代理
3. 或切换到 zkware 数据源
4. 或使用示例数据进行离线测试

## 集成到工作流

### 企业微信通知

配置 Webhook 后，数据缺失时会自动发送告警：

```bash
WECOM_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx
```

### 读取分析报告

在 Obsidian 或其他工具中读取报告：
```bash
# 获取最新报告路径
LATEST_REPORT=$(ls -t output/1h_analysis/*.md | head -1)
cat "$LATEST_REPORT"
```

### 自动化脚本

```bash
#!/bin/bash
# 市场分析自动化脚本

cd ~/.openclaw/workspace/skills/market_researcher

# 同步数据
python3 scripts/sync_data.py

# 执行分析
python3 scripts/analyze.py 1h

# 复制报告到 Obsidian
cp output/1h_analysis/*.md /mnt/d/obsidian_vault/zkware/market_analysis/
```
