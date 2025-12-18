#!/bin/bash

# ORIM GUI 启动脚本
# 用于演示 Alice to Bob 端到端文件传输

cd "$(dirname "$0")/orim_engine"
source ~/miniconda3/bin/activate orim_env

echo "🚀 启动 ORIM 端到端文件传输 GUI..."
echo "💡 使用说明："
echo "   左侧窗口 = Alice (发送方)"
echo "   右侧窗口 = Bob (接收方)"
echo ""
echo "📝 操作流程："
echo "   1. Alice: 点击 '📁 选择文件' 选择要发送的文件"
echo "   2. Alice: 点击 '🚀 加密并上传' 加密文件并上传到IPFS"
echo "   3. Alice: 查看生成的CID，文件已进入发送队列"
echo "   4. Bob: 等待接收CID（从区块链解码）"
echo "   5. Bob: 选中接收到的CID，点击 '⬇️ 下载选中文件'"
echo "   6. Bob: 文件自动从IPFS下载并解密"
echo ""
echo "🧪 测试文件: /tmp/alice_secret_message.txt (791 bytes)"
echo ""

python3 orim_gui.py
