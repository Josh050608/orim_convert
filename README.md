# 🚀 ORIM 隐蔽文件传输系统

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9+-green.svg)](https://python.org)
[![Bitcoin](https://img.shields.io/badge/bitcoin-modified-orange.svg)](bitcoin/)

基于区块链的端到端加密文件传输系统，使用 IPFS + Bitcoin 隐蔽信道实现完全隐蔽的文件传输。

---

## ⚡ 快速开始

```bash
# 1. 启动完整系统（含 GUI）
./start_demo.sh

# 2. 或仅启动 GUI 界面
./start_gui.sh

# 3. 停止所有服务
./stop.sh
```

---

## 📚 详细文档

- **项目总结**: [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) - 完整的技术实现和架构说明
- **GUI 使用指南**: [docs/GUI_USER_GUIDE.md](docs/GUI_USER_GUIDE.md) - 图形界面操作指南
- **技术文档**: [docs/ORIM_README.md](docs/ORIM_README.md) - 深入的技术细节

---

## 🔧 环境配置

### 1. 安装系统依赖

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

### 2. 创建 Python 环境

```bash
# 安装 Miniconda（如果尚未安装）
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh

# 创建并激活环境
conda create -n orim_env python=3.9 -y
conda activate orim_env

# 安装 Python 依赖
pip install pyzmq cryptography requests ipfshttpclient
```

**依赖说明**:
- `pyzmq`: ZMQ 消息队列（ORIM Server 通信）
- `cryptography`: Fernet AES-256 加密
- `requests`: IPFS HTTP API 调用
- `ipfshttpclient`: IPFS Python 客户端

---

### 3. 安装和配置 IPFS

```bash
# macOS
brew install ipfs

# Linux
wget https://dist.ipfs.tech/kubo/v0.38.1/kubo_v0.38.1_linux-amd64.tar.gz
tar -xvzf kubo_v0.38.1_linux-amd64.tar.gz
cd kubo
sudo bash install.sh

# 初始化 IPFS
ipfs init

# 启动 IPFS daemon（需要保持运行）
ipfs daemon
```

**后台运行 IPFS**:
```bash
nohup ipfs daemon > /tmp/ipfs_daemon.log 2>&1 &
```

**验证 IPFS**:
```bash
ipfs id
# 应该显示你的 IPFS 节点 ID
```

---

### 4. 编译 Bitcoin Core

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

## 🚀 启动系统

### 完整启动（推荐）

```bash
# 启动所有服务 + GUI
./start_demo.sh
```

**启动内容**:
1. ORIM Server (编码服务)
2. Decoder Service (解码服务)
3. Bitcoin Regtest 网络 (2个节点)
4. Traffic Bot (自动挖矿)
5. Alice-Bob GUI 界面

### GUI 使用说明

**Alice (左侧窗口)**:
1. 点击 `📁 选择文件` 选择要发送的文件
2. 点击 `🚀 加密并上传` 加密并上传到 IPFS
3. 查看生成的 CID（文件索引）
4. 等待传输（10-60秒）

**Bob (右侧窗口)**:
1. 自动检测接收到的 CID
2. 选中 CID 行
3. 点击 `⬇️ 下载选中文件`
4. 文件自动解密保存到 `storage/downloads/`

---

## 📊 系统监控

```bash
# 查看日志
tail -f storage/orim_server.log    # ORIM 服务器
tail -f storage/decoder.log         # 解码服务
tail -f storage/traffic.log         # 流量机器人

# 查看区块链状态
./bitcoin/src/bitcoin-cli -regtest -datadir=/tmp/bitcoin_sender \
  -rpcuser=test -rpcpassword=test getblockchaininfo

# 查看数据库
sqlite3 storage/orim.db "SELECT * FROM outgoing_messages LIMIT 5"
sqlite3 storage/orim.db "SELECT * FROM decoded_messages LIMIT 5"

# 查看 IPFS 状态
ipfs id
ipfs swarm peers
```

---

## 🐛 故障排查

### IPFS 相关

**问题**: "IPFS download failed: 500"
```bash
# 检查 IPFS daemon 是否运行
ps aux | grep "ipfs daemon"

# 重启 IPFS
ipfs shutdown
nohup ipfs daemon > /tmp/ipfs_daemon.log 2>&1 &
sleep 3
```

### 数据库锁定

**问题**: "database is locked"
```bash
./stop.sh
rm -f storage/*.lock storage/*.db-journal
./start_demo.sh
```

### 密钥问题

**问题**: "No encryption key found for CID"
```bash
# 检查密钥文件
cat storage/crypto_keys.json

# 密钥应该包含该 CID
```

### 端口占用

**问题**: 启动失败 - 端口被占用
```bash
# 清理所有进程
./stop.sh
pkill -9 bitcoind
pkill -9 python

# 重新启动
./start_demo.sh
```

---

## 📖 技术栈

- **区块链**: Bitcoin Core (Modified) - Regtest 模式
- **存储**: IPFS (Kubo 0.38.1) - 分布式文件系统
- **加密**: Fernet (AES-256-CBC + HMAC-SHA256)
- **编码**: Complete Binary Tree Variable-Length Encoding
- **数据库**: SQLite 3
- **界面**: Tkinter (Python GUI)
- **通信**: ZMQ (进程间通信)

---

## 🎯 项目特点

✅ **完全隐蔽**: 无法从区块链检测文件传输行为  
✅ **端到端加密**: AES-256 加密，密钥不经网络  
✅ **分布式存储**: IPFS 去中心化存储  
✅ **高效编码**: 99%+ 编码效率  
✅ **用户友好**: 图形界面，零技术门槛  

---

## 📞 获取帮助

- **项目总结**: [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)
- **使用指南**: [docs/GUI_USER_GUIDE.md](docs/GUI_USER_GUIDE.md)
- **技术文档**: [docs/ORIM_README.md](docs/ORIM_README.md)

---

## 📄 许可证

MIT License

---

**项目状态**: ✅ 生产就绪  
**最后更新**: 2025年12月





