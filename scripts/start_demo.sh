#!/bin/bash
# ORIM GUI Demo Launcher
# 此脚本初始化环境并启动图形界面

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}   ORIM 隐蔽通信系统 - 本地演示启动器   ${NC}"
echo -e "${YELLOW}========================================${NC}"

# 0. 清理旧进程和数据
echo -e "\n${YELLOW}[0/4] 清理环境...${NC}"
pkill -f "bitcoind.*regtest" || true
pkill -f "orim_server.py" || true
rm -rf /tmp/bitcoin_sender /tmp/bitcoin_receiver
rm -f orim_engine/orim.db # 清除旧数据库，从头开始

# 1. 启动 ORIM Server (Python 后端)
echo -e "\n${YELLOW}[1/4] 启动 ORIM 核心服务器...${NC}"
# 尝试激活 conda 环境 (如果需要)
source ~/miniconda3/etc/profile.d/conda.sh 2>/dev/null || source ~/anaconda3/etc/profile.d/conda.sh 2>/dev/null || true
conda activate orim_env 2>/dev/null || true

cd orim_engine
# 初始化数据库并后台运行
python3 orim_server.py --db orim.db > /tmp/orim_server.log 2>&1 &
SERVER_PID=$!
sleep 2

if ! ps -p $SERVER_PID > /dev/null; then
    echo -e "${RED}ORIM Server 启动失败，请检查日志 /tmp/orim_server.log${NC}"
    exit 1
fi
echo -e "${GREEN}✓ ORIM Server 运行中 (PID: $SERVER_PID)${NC}"

# 2. 启动比特币节点 (C++ 后端)
echo -e "\n${YELLOW}[2/4] 启动比特币 Regtest 节点...${NC}"
cd ..

# 启动发送方 (Sender)
mkdir -p /tmp/bitcoin_sender
./bitcoin/src/bitcoind -regtest -datadir=/tmp/bitcoin_sender \
    -port=18444 -rpcport=18443 -rpcuser=test -rpcpassword=test \
    -enableorim -daemon -fallbackfee=0.00001 > /dev/null 2>&1
echo -e "${GREEN}✓ 发送节点 (Sender) 已启动${NC}"

# 启动接收方 (Receiver)
mkdir -p /tmp/bitcoin_receiver
./bitcoin/src/bitcoind -regtest -datadir=/tmp/bitcoin_receiver \
    -port=18445 -rpcport=18445 -rpcuser=test -rpcpassword=test \
    -connect=127.0.0.1:18444 -enableorim -daemon -fallbackfee=0.00001 > /dev/null 2>&1
echo -e "${GREEN}✓ 接收节点 (Receiver) 已启动${NC}"

# 等待节点初始化
sleep 3

# 3. 建立连接并挖矿初始化
echo -e "\n${YELLOW}[3/4] 初始化区块链网络...${NC}"
# 创建钱包
./bitcoin/src/bitcoin-cli -regtest -datadir=/tmp/bitcoin_sender -rpcuser=test -rpcpassword=test \
    createwallet "testwallet" > /dev/null 2>&1 || true

# 挖 101 个块 (让币成熟，Sender 才有钱发交易)
ADDR=$(./bitcoin/src/bitcoin-cli -regtest -datadir=/tmp/bitcoin_sender -rpcuser=test -rpcpassword=test getnewaddress)
echo -e "正在生成初始区块 (这可能需要几秒钟)..."
./bitcoin/src/bitcoin-cli -regtest -datadir=/tmp/bitcoin_sender -rpcuser=test -rpcpassword=test \
    generatetoaddress 101 "$ADDR" > /dev/null
echo -e "${GREEN}✓ 区块链初始化完成 (高度: 101)${NC}"

# 4. 启动 GUI
echo -e "\n${YELLOW}[4/4] 启动图形控制台...${NC}"
echo -e "${GREEN}现在你可以通过图形界面发送隐蔽消息了！${NC}"
echo -e "提示: 关闭图形界面将自动停止所有后台进程。"

cd orim_engine
python3 orim_gui.py

# 退出清理
echo -e "\n${YELLOW}正在停止服务...${NC}"
pkill -f "bitcoind.*regtest" || true
kill $SERVER_PID || true
echo -e "${GREEN}演示结束${NC}"
