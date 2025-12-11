#!/bin/bash
# ORIM Covert Channel Integration Test Script
# Tests end-to-end message transmission through Bitcoin P2P network

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}ORIM Integration Test${NC}"
echo -e "${YELLOW}========================================${NC}"

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}Cleaning up...${NC}"
    pkill -f "bitcoind.*regtest" || true
    pkill -f "orim_server.py" || true
    sleep 2
    rm -rf /tmp/bitcoin_sender /tmp/bitcoin_receiver
    echo -e "${GREEN}Cleanup complete${NC}"
}

trap cleanup EXIT

# Step 1: Start ORIM Server
echo -e "\n${YELLOW}[1/6] Starting ORIM Server...${NC}"
# Use conda environment
source ~/miniconda3/etc/profile.d/conda.sh 2>/dev/null || source ~/anaconda3/etc/profile.d/conda.sh 2>/dev/null || true
conda activate orim_env 2>/dev/null || true
python3 ../orim_engine/orim_server.py > /tmp/orim_server.log 2>&1 &
ORIM_PID=$!
sleep 3

if ! ps -p $ORIM_PID > /dev/null; then
    echo -e "${RED}Failed to start ORIM server${NC}"
    cat /tmp/orim_server.log
    exit 1
fi
echo -e "${GREEN}✓ ORIM Server started (PID: $ORIM_PID)${NC}"

# Step 2: Initialize sender node
echo -e "\n${YELLOW}[2/6] Starting sender node...${NC}"
rm -rf /tmp/bitcoin_sender
mkdir -p /tmp/bitcoin_sender
../bitcoin/src/bitcoind -regtest -datadir=/tmp/bitcoin_sender \
    -port=18444 -rpcport=18443 -rpcuser=test -rpcpassword=test \
    -enableorim -daemon -fallbackfee=0.00001 > /tmp/sender.log 2>&1
sleep 5
echo -e "${GREEN}✓ Sender node started (ORIM enabled)${NC}"

# Step 3: Initialize receiver node
echo -e "\n${YELLOW}[3/6] Starting receiver node...${NC}"
rm -rf /tmp/bitcoin_receiver
mkdir -p /tmp/bitcoin_receiver
../bitcoin/src/bitcoind -regtest -datadir=/tmp/bitcoin_receiver \
    -port=18445 -rpcport=18445 -rpcuser=test -rpcpassword=test \
    -connect=127.0.0.1:18444 -enableorim -daemon -fallbackfee=0.00001 > /tmp/receiver.log 2>&1
sleep 5
echo -e "${GREEN}✓ Receiver node started (ORIM enabled)${NC}"

# Step 4: Generate blocks to establish connection
echo -e "\n${YELLOW}[4/6] Generating initial blocks...${NC}"
../bitcoin/src/bitcoin-cli -regtest -datadir=/tmp/bitcoin_sender -rpcuser=test -rpcpassword=test \
    createwallet "testwallet" > /dev/null 2>&1 || true
ADDR=$(../bitcoin/src/bitcoin-cli -regtest -datadir=/tmp/bitcoin_sender -rpcuser=test -rpcpassword=test \
    getnewaddress)
../bitcoin/src/bitcoin-cli -regtest -datadir=/tmp/bitcoin_sender -rpcuser=test -rpcpassword=test \
    generatetoaddress 101 "$ADDR" > /dev/null
sleep 5
echo -e "${GREEN}✓ Generated 101 blocks${NC}"

# Check connection
echo -e "\n${YELLOW}Checking peer connections...${NC}"
PEER_COUNT=$(../bitcoin/src/bitcoin-cli -regtest -datadir=/tmp/bitcoin_sender -rpcuser=test -rpcpassword=test \
    getconnectioncount)
echo -e "Sender peer count: $PEER_COUNT"

# Step 5: Send covert message
echo -e "\n${YELLOW}[5/6] Sending covert message via ORIM...${NC}"
TEST_MESSAGE="Hello"
echo -e "Message: ${GREEN}$TEST_MESSAGE${NC}"

# Add message to ORIM database (use conda environment)
conda activate orim_env 2>/dev/null || true
python3 ../orim_engine/orim_server.py --db orim.db --add-message "$TEST_MESSAGE"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Message queued successfully${NC}"
    
    # Check the message in database
    echo -e "\n${YELLOW}Queued messages in database:${NC}"
    sqlite3 orim.db "SELECT id, message, bits, status FROM outgoing_messages;" 2>/dev/null || true
else
    echo -e "${RED}✗ Failed to queue message${NC}"
fi

# Trigger INV messages by creating and broadcasting transactions
echo -e "\n${YELLOW}Triggering INV messages with transactions...${NC}"
echo -e "Message 'Hello' needs ~40 bits, creating 120 transactions in batches..."

for batch in {1..6}; do
    echo -e "\n  Batch $batch: Creating 20 transactions..."
    for i in {1..20}; do
        TX_ADDR=$(../bitcoin/src/bitcoin-cli -regtest -datadir=/tmp/bitcoin_sender -rpcuser=test -rpcpassword=test getnewaddress)
        ../bitcoin/src/bitcoin-cli -regtest -datadir=/tmp/bitcoin_sender -rpcuser=test -rpcpassword=test \
            sendtoaddress "$TX_ADDR" 0.01 > /dev/null 2>&1 || true
    done
    echo -e "  Waiting 5s for propagation..."
    sleep 5
done

echo -e "\n${YELLOW}Mining blocks to trigger block INV messages...${NC}"
for i in {1..15}; do
    ../bitcoin/src/bitcoin-cli -regtest -datadir=/tmp/bitcoin_sender -rpcuser=test -rpcpassword=test \
        generatetoaddress 1 "$ADDR" > /dev/null
    sleep 2
done

echo -e "\n${YELLOW}Final wait for decoding (15s)...${NC}"
sleep 15

# Step 6: Check received messages
echo -e "\n${YELLOW}[6/6] Checking received messages...${NC}"
echo -e "\n${YELLOW}Incoming messages in database:${NC}"
RECEIVED=$(sqlite3 orim.db "SELECT id, received_at, bits FROM incoming_messages;" 2>/dev/null)
echo "$RECEIVED"

echo -e "\n${YELLOW}Decoded messages in database:${NC}"
DECODED=$(sqlite3 orim.db "SELECT id, decoded_at, message FROM decoded_messages ORDER BY id DESC LIMIT 5;" 2>/dev/null)
echo "$DECODED"

if echo "$DECODED" | grep -q "$TEST_MESSAGE"; then
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}✓ SUCCESS! Message received correctly!${NC}"
    echo -e "${GREEN}========================================${NC}"
else
    echo -e "\n${RED}========================================${NC}"
    echo -e "${RED}✗ FAILED: Message not received${NC}"
    echo -e "${RED}========================================${NC}"
    echo -e "\n${YELLOW}ORIM Server Log:${NC}"
    tail -50 /tmp/orim_server.log
    
    echo -e "\n${YELLOW}Outgoing messages status:${NC}"
    sqlite3 orim.db "SELECT * FROM outgoing_messages;" 2>/dev/null || true
fi

echo -e "\n${YELLOW}Press Ctrl+C to exit and cleanup...${NC}"
read -r
