#!/bin/bash

# 同步远程服务器数据脚本
# 用途：从 zkware@192.168.1.10 同步 trading_crypto_bot 数据到本地
# 只同步 .env 中 TOP_SYMBOLS 配置的代币

set -e

# 加载 .env 文件
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

if [ -f "${ENV_FILE}" ]; then
    export $(grep -v '^#' "${ENV_FILE}" | xargs) 2>/dev/null
fi

# 如果未配置 TOP_SYMBOLS，使用默认列表
if [ -z "${TOP_SYMBOLS}" ]; then
    TOP_SYMBOLS="BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT,DOGEUSDT,ADAUSDT,FILUSDT"
fi

# 转换为数组
IFS=',' read -ra SYMBOLS <<< "${TOP_SYMBOLS}"

# 配置
REMOTE_USER="zkware"
REMOTE_HOST="192.168.1.10"
REMOTE_BASE_PATH="/home/zkware/workspace/go_projects/trading_crypto_bot/data/binance/futures/um/daily"
LOCAL_PATH="/home/zkware/workspace/shared_data"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
 echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
 echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
 echo -e "${RED}[ERROR]${NC} $1"
}

# 检查 SSH 连接
check_ssh() {
 log_info "检查 SSH 连接..."
 if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "${REMOTE_USER}@${REMOTE_HOST}" "echo 'SSH 连接正常'" > /dev/null 2>&1; then
 log_error "无法连接到远程服务器 ${REMOTE_HOST}"
 exit 1
 fi
 log_info "SSH 连接正常"
}

# 确保本地目录存在
ensure_local_dir() {
 if [ ! -d "${LOCAL_PATH}" ]; then
 log_info "创建本地目录：${LOCAL_PATH}"
 mkdir -p "${LOCAL_PATH}"
 fi
}

# 同步数据（逐个代币）
sync_data() {
 log_info "开始同步数据..."
 log_info "远程服务器：${REMOTE_USER}@${REMOTE_HOST}"
 log_info "本地目录：${LOCAL_PATH}"
 log_info "同步代币：${TOP_SYMBOLS}"

 for symbol in "${SYMBOLS[@]}"; do
 log_info "同步 ${symbol}..."
 
 rsync -avz --progress \
 -e "ssh -o StrictHostKeyChecking=no" \
 "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_BASE_PATH}/${symbol}/" \
 "${LOCAL_PATH}/${symbol}/"
 
 if [ $? -eq 0 ]; then
 log_info "${symbol} 同步完成"
 else
 log_warn "${symbol} 同步失败（跳过）"
 fi
 done

 log_info "所有代币同步完成"
}

# 显示同步后的文件列表
show_result() {
 log_info "同步后的文件列表:"
 ls -lh "${LOCAL_PATH}" | head -20
}

# 主函数
main() {
 echo "=========================================="
 echo " 远程数据同步脚本"
 echo "=========================================="

 check_ssh
 ensure_local_dir
 sync_data
 show_result

 echo "=========================================="
 log_info "同步完成!"
}

# 执行
main "$@"
