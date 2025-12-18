#!/bin/bash
# ORIM GUI Demo Launcher (Debug Edition)
# 功能：初始化环境、启动节点、自动生成背景流量（可配置参数）、启动图形界面

set -e

# ========================================================
# 🔧 [调试配置区域] - 修改这里来调整流量强度
# ========================================================

# 1. 每次循环发送的最大交易数量 (1 ~ N)
# 数值越大，产生的 INV 消息包含的 Hash 条数越多
TX_BATCH_MAX=10

# 2. 挖矿概率 (1/N)
# 例如设置为 5，代表有 1/5 (20%) 的概率挖一个块
# 如果设置为 1，代表每次循环必定挖一个块 (极速确认)
BLOCK_PROBABILITY=5

# 3. 流量生成间隔 (秒)
# 越小越快。设置为 0.5 可以产生高频流量
TRAFFIC_INTERVAL=2

# ========================================================

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}   ORIM 隐蔽通信系统 - 调试版启动器       ${NC}"
echo -e "${YELLOW}========================================${NC}"
echo -e "${BLUE}当前配置:${NC}"
echo -e "  - 交易批次大小: 1 ~ $TX_BATCH_MAX 笔"
echo -e "  - 挖矿概率: 1/$BLOCK_PROBABILITY"
echo -e "  - 循环间隔: $TRAFFIC_INTERVAL 秒"

# ---------------------------------------------------------
# 0. 清理旧进程和数据
# ---------------------------------------------------------
echo -e "\n${YELLOW}[0/5] 清理环境...${NC}"

# 1. 强制杀死所有相关进程 (-9 表示不给喘息机会，直接带走)
pkill -9 -f "bitcoind.*regtest" || true
pkill -9 -f "orim_server.py" || true
# 同样强制杀死旧的流量循环
pkill -9 -f "sleep $TRAFFIC_INTERVAL" || true 
pkill -9 -f "sleep 2" || true

# 2. 【关键】等待操作系统释放文件锁
# 给 OS 一点时间回收 18444 端口和文件句柄
sleep 2

# 3. 删除数据
rm -rf /tmp/bitcoin_sender /tmp/bitcoin_receiver
rm -f orim_engine/orim.db

# ---------------------------------------------------------
# 1. 启动 ORIM Server (Python 后端)
# ---------------------------------------------------------
echo -e "\n${YELLOW}[1/5] 启动 ORIM 核心服务器...${NC}"
source ~/miniconda3/etc/profile.d/conda.sh 2>/dev/null || source ~/anaconda3/etc/profile.d/conda.sh 2>/dev/null || true
conda activate orim_env 2>/dev/null || true

cd orim_engine

python3 orim_server.py --db orim.db > /tmp/orim_server.log 2>&1 &
SERVER_PID=$!
sleep 2

if ! ps -p $SERVER_PID > /dev/null; then
    echo -e "${RED}ORIM Server 启动失败，请检查日志 /tmp/orim_server.log${NC}"
    exit 1
fi
echo -e "${GREEN}✓ ORIM Server 运行中 (PID: $SERVER_PID)${NC}"

# ---------------------------------------------------------
# 2. 启动比特币节点 (C++ 后端)
# ---------------------------------------------------------
echo -e "\n${YELLOW}[2/5] 启动比特币 Regtest 节点...${NC}"
cd ..

# 启动发送方
mkdir -p /tmp/bitcoin_sender
./bitcoin/src/bitcoind -regtest -datadir=/tmp/bitcoin_sender \
    -port=18444 -rpcport=18443 -rpcuser=test -rpcpassword=test \
    -enableorim -daemon -fallbackfee=0.00001 > /dev/null 2>&1
echo -e "${GREEN}✓ 发送节点 (Sender) 已启动${NC}"

# 启动接收方
mkdir -p /tmp/bitcoin_receiver
./bitcoin/src/bitcoind -regtest -datadir=/tmp/bitcoin_receiver \
    -port=18445 -rpcport=18445 -rpcuser=test -rpcpassword=test \
    -connect=127.0.0.1:18444 -enableorim -daemon -fallbackfee=0.00001 > /dev/null 2>&1
echo -e "${GREEN}✓ 接收节点 (Receiver) 已启动${NC}"


sleep 3

# ---------------------------------------------------------
# 3. 建立连接并挖矿初始化
# ---------------------------------------------------------
echo -e "\n${YELLOW}[3/5] 初始化区块链网络...${NC}"
CLI="./bitcoin/src/bitcoin-cli -regtest -datadir=/tmp/bitcoin_sender -rpcuser=test -rpcpassword=test"

# 创建钱包
$CLI createwallet "testwallet" > /dev/null 2>&1 || true

# 挖 101 个块 (让币成熟)
ADDR=$($CLI getnewaddress)
echo -e "正在生成初始区块 (这可能需要几秒钟)..."
$CLI generatetoaddress 101 "$ADDR" > /dev/null
echo -e "${GREEN}✓ 区块链初始化完成 (高度: 101)${NC}"

# ---------------------------------------------------------
# 4. [动态] 启动后台流量机器人
# ---------------------------------------------------------
echo -e "\n${YELLOW}[4/5] 启动自动流量生成器...${NC}"

(
    while true; do
        # A. 使用全局变量生成交易
        # RANDOM % N 生成 0 到 N-1 的数，所以 +1 变成 1 到 N
        BATCH=$((1 + RANDOM % TX_BATCH_MAX))
        
        for ((i=0; i<BATCH; i++)); do
            $CLI sendtoaddress "$ADDR" 0.001 >/dev/null 2>&1
        done
        
        # B. 使用全局变量决定是否挖矿
        if [ $((RANDOM % BLOCK_PROBABILITY)) -eq 0 ]; then
            $CLI generatetoaddress 1 "$ADDR" >/dev/null 2>&1
        fi
        
        # C. 使用全局变量控制速度
        sleep $TRAFFIC_INTERVAL
    done
) &
TRAFFIC_PID=$!
echo -e "${BLUE}⚡ 流量机器人已启动 (PID: $TRAFFIC_PID)${NC}"

# ---------------------------------------------------------
# 5. 启动 GUI
# ---------------------------------------------------------
echo -e "\n${YELLOW}[5/5] 启动图形控制台...${NC}"
cd orim_engine
python3 orim_gui.py

# ---------------------------------------------------------
# 退出清理
# ---------------------------------------------------------
echo -e "\n${YELLOW}正在停止服务...${NC}"
pkill -f "bitcoind.*regtest" || true
kill $SERVER_PID 2>/dev/null || true
kill $TRAFFIC_PID 2>/dev/null || true
echo -e "${GREEN}演示结束${NC}"
