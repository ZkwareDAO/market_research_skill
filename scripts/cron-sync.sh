#!/bin/bash
# 数据同步 + 重采样 cron 脚本
# 每 15 分钟执行一次

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/../logs"
mkdir -p "$LOG_DIR"

LOG_FILE="$LOG_DIR/sync-$(date +\%Y-\%m-\%d).log"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始同步..." >> "$LOG_FILE"

cd "$SCRIPT_DIR" && /usr/bin/python3 sync_data.py >> "$LOG_FILE" 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 同步完成" >> "$LOG_FILE"
