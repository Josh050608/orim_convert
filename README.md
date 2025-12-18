# 🚀 ORIM 隐蔽文件传输系统

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9+-green.svg)](https://python.org)
[![Bitcoin](https://img.shields.io/badge/bitcoin-modified-orange.svg)](bitcoin/)

基于区块链的端到端加密文件传输系统，使用 IPFS + Bitcoin 隐蔽信道实现完全隐蔽的文件传输。

---

## ⚡ 快速开始

### 🧪 快速测试（推荐首次使用）
```bash
./test_e2e.py
```

### 🎨 启动 GUI 演示
```bash
./demo_gui.sh
```

### 🌐 启动完整系统
```bash
./start_demo.sh
```

---

## 📚 详细文档

- **GUI 使用指南**: [docs/GUI_USER_GUIDE.md](docs/GUI_USER_GUIDE.md)
- **集成完成报告**: [docs/GUI_INTEGRATION_COMPLETE.md](docs/GUI_INTEGRATION_COMPLETE.md)
- **技术实现文档**: [docs/ORIM_README.md](docs/ORIM_README.md)

---

## 1. 安装系统依赖

### Ubuntu/Debian
```bash
sudo apt update
sudo apt install -y \
    build-essential \
    libtool \
    autotools-dev \
    automake \
    pkg-config \
    bsdmainutils \
    python3 \
    libssl-dev \
    libevent-dev \
    libboost-all-dev \
    libzmq3-dev \
    libsqlite3-dev
```

### macOS
```bash
brew install automake libtool boost pkg-config libevent zeromq sqlite
```

---

## 2. 创建 Python 环境

```bash
# 安装 Miniconda（如果尚未安装）
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh

# 创建并激活环境
conda create -n orim_env python=3.9 -y
conda activate orim_env

# 安装 Python 依赖
pip install pyzmq
```

---

## 3. 编译 Bitcoin Core

```bash
cd bitcoin
# 生成配置脚本
./autogen.sh

# 重新配置，禁用miniupnpc
./configure \
    --with-incompatible-bdb \
    --enable-zmq \
    --without-miniupnpc \
    CPPFLAGS="-I/usr/local/include" \
    LDFLAGS="-L/usr/local/lib"

# 编译（使用多核加速）
make -j$(nproc)  # Linux
# 或
make -j$(sysctl -n hw.ncpu)  # macOS
```

**编译时间**：首次约 15-30 分钟

---

## 4. 运行集成测试

```bash
# 确保在项目根目录
cd scripts/
./test_orim_integration.sh
```

**测试流程**：
1. 启动 ORIM Python 服务器
2. 启动发送方和接收方 Bitcoin 节点
3. 生成初始区块
4. 发送测试消息 "Hello"
5. 验证消息接收

**预期结果**：
```
========================================
✓ SUCCESS! Message received correctly!
========================================
```

---

## 常见问题

### 问题 1：configure 报错 "ZMQ not found"
```bash
sudo apt install libzmq3-dev  # Ubuntu
brew install zeromq           # macOS
```

### 问题 2：Python 找不到 zmq 模块
```bash
conda activate orim_env
pip install pyzmq
```

### 问题 3：测试失败 - 端口占用
```bash
# 清理旧进程
pkill -9 bitcoind
pkill -9 orim_server.py
```

---





