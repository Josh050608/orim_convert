#!/bin/bash
# 强力停止所有 ORIM 相关进程

echo "正在执行强力清理..."

# 1. 杀进程
pkill -9 -f "bitcoind"
pkill -9 -f "python3.*orim"
pkill -9 -f "python3.*traffic"
pkill -9 -f "decoder"
pkill -9 -f "start_demo"

# 2. 也是最重要的：删除 ZMQ 锁和临时文件
rm -f storage/*.lock

echo "✓ 所有进程已击杀，端口已释放。"