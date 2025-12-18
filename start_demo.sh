#!/bin/bash
# ORIM GUI Demo Launcher (Fixed Path Version)

set -e

# ========================================================
# 📍 [关键修复] 获取脚本所在的绝对路径
# ========================================================
# 无论你在哪里运行脚本，或者脚本中间cd到哪里，这个变量永远指向项目根目录
ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

echo -e "📂 项目根目录锁定为: ${ROOT_DIR}"

# ========================================================
# 🔧 [配置区]
# ========================================================
TX_BATCH_MAX=50
BLOCK_PROBABILITY=2
TRAFFIC_INTERVAL=1

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# ========================================================
# 🧹 [终极清理函数 - 绝对路径版]
# ========================================================
deep_clean() {
    echo -e "${RED}正在执行终极清理...${NC}"
    
    # 1. 先杀进程 (使用 -9 强制终止)
    pkill -9 -f "bitcoind" || true
    pkill -9 -f "python" || true  # Kill all python processes related to the project
    pkill -9 -f "orim" || true
    pkill -9 -f "traffic_bot" || true
    
    sleep 2  # Give OS time to release locks
    
    # 2. 清理比特币数据 (使用绝对路径)
    echo "[Deep Clean] Removing Bitcoin data directories..."
    rm -rf /tmp/bitcoin_sender
    rm -rf /tmp/bitcoin_receiver
    
    # 3. 清理 storage 目录所有数据库和日志文件 (使用绝对路径!)
    echo "[Deep Clean] Cleaning storage directory: $ROOT_DIR/storage/"
    rm -f "$ROOT_DIR/storage/"*.db
    rm -f "$ROOT_DIR/storage/"*.log
    rm -f "$ROOT_DIR/storage/"*.lock
    rm -f "$ROOT_DIR/storage/"*.db-journal
    rm -f "$ROOT_DIR/storage/"*.db-shm
    rm -f "$ROOT_DIR/storage/"*.db-wal
    
    # 4. 清理引擎目录残余
    echo "[Deep Clean] Cleaning orim_engine directory..."
    rm -f "$ROOT_DIR/orim_engine/orim.db"
    rm -f "$ROOT_DIR/orim_engine/"*.log
    rm -rf "$ROOT_DIR/orim_engine/__pycache__"
    
    # 5. 重建目录
    mkdir -p "$ROOT_DIR/storage"
    mkdir -p /tmp/bitcoin_sender
    mkdir -p /tmp/bitcoin_receiver
    
    echo -e "${GREEN}✓ 环境已归零 (Absolute Paths Cleaned)${NC}"
}

# 退出时的清理
cleanup_on_exit() {
    echo -e "\n${YELLOW}演示结束，正在停止所有服务...${NC}"
    
    # Kill specific PIDs if they exist
    [ -n "$SERVER_PID" ] && kill $SERVER_PID 2>/dev/null || true
    [ -n "$DECODER_PID" ] && kill $DECODER_PID 2>/dev/null || true
    [ -n "$TRAFFIC_PID" ] && kill $TRAFFIC_PID 2>/dev/null || true
    
    # Kill bitcoind nodes
    pkill -f "bitcoind.*regtest" || true
    
    # Kill traffic_bot specifically
    pkill -f "traffic_bot.py" || true
    
    # Final cleanup of any remaining python/orim processes
    pkill -f "orim_server.py" || true
    pkill -f "orim_gui.py" || true
    
    echo -e "${GREEN}所有服务已停止 (数据和日志已保留)${NC}"
}

trap cleanup_on_exit EXIT INT TERM

# ========================================================
# 🚀 [启动流程]
# ========================================================

# 0. 执行深度清理
echo -e "\n${YELLOW}[0/5] 初始化全新环境...${NC}"
deep_clean

# 1. 启动 ORIM Server (使用 ROOT_DIR 拼接路径)
echo -e "\n${YELLOW}[1/5] 启动 ORIM 核心服务器...${NC}"
source ~/miniconda3/etc/profile.d/conda.sh 2>/dev/null || source ~/anaconda3/etc/profile.d/conda.sh 2>/dev/null || true
conda activate orim_env 2>/dev/null || true

cd "$ROOT_DIR/orim_engine"

# 注意：这里我们明确告诉 Server 数据库的绝对路径
python3 orim_server.py --db "$ROOT_DIR/storage/orim.db" > "$ROOT_DIR/storage/orim_server.log" 2>&1 &
SERVER_PID=$!
sleep 2
echo -e "${GREEN}✓ Server 运行中 (PID: $SERVER_PID)${NC}"

# 1.5 启动解码器
echo -e "\n${YELLOW}[1.5/5] 启动增量解码服务...${NC}"
python3 decoder_service.py > "$ROOT_DIR/storage/decoder.log" 2>&1 &
DECODER_PID=$!
echo -e "${GREEN}✓ Decoder 运行中 (PID: $DECODER_PID)${NC}"

# 2. 启动比特币 Regtest
echo -e "\n${YELLOW}[2/5] 启动全新的比特币网络...${NC}"
cd "$ROOT_DIR"  # 回到根目录

./bitcoin/src/bitcoind -regtest -datadir=/tmp/bitcoin_sender \
    -port=18444 -rpcport=18443 -rpcuser=test -rpcpassword=test \
    -enableorim -daemon -fallbackfee=0.00001 > /dev/null 2>&1

./bitcoin/src/bitcoind -regtest -datadir=/tmp/bitcoin_receiver \
    -port=18445 -rpcport=18445 -rpcuser=test -rpcpassword=test \
    -connect=127.0.0.1:18444 -enableorim -daemon -fallbackfee=0.00001 > /dev/null 2>&1

echo -e "${GREEN}✓ 比特币节点已启动${NC}"
sleep 3

# 3. 初始化区块链
echo -e "\n${YELLOW}[3/5] 重新挖掘创世区块...${NC}"
CLI="./bitcoin/src/bitcoin-cli -regtest -datadir=/tmp/bitcoin_sender -rpcuser=test -rpcpassword=test"

$CLI createwallet "testwallet" > /dev/null 2>&1 || true
ADDR=$($CLI getnewaddress)
$CLI generatetoaddress 101 "$ADDR" > /dev/null
echo -e "${GREEN}✓ 新链高度: 101${NC}"

# 4. 启动 Python 流量机器人 (替代旧的 Bash 循环)
echo -e "\n${YELLOW}[4/5] 启动 Python 流量生成器...${NC}"
cd "$ROOT_DIR/orim_engine"

if [ -f "traffic_bot.py" ]; then
    python3 traffic_bot.py > "$ROOT_DIR/storage/traffic.log" 2>&1 &
    TRAFFIC_PID=$!
    echo -e "${GREEN}✓ Python 流量机器人已启动 (PID: $TRAFFIC_PID)${NC}"
else
    echo -e "${RED}ERROR: traffic_bot.py not found!${NC}"
    exit 1
fi

# 5. 启动 GUI
echo -e "\n${YELLOW}[5/5] 启动图形控制台...${NC}"
# 此时已经在 orim_engine 目录了
python3 orim_gui.py