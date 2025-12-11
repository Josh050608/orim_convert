# ORIM项目环境部署与编译指南

**区块链隐蔽信道 ORIM 项目 - 第一部分：环境搭建与编译**

-----

## 1\. 核心依赖安装

ORIM 项目基于 Bitcoin Core v25.0，并添加了 ZeroMQ 和 SQLite 支持。

### Ubuntu/Debian 系统

```bash
# 更新软件源
sudo apt update && sudo apt upgrade -y

# 安装编译工具链
sudo apt install -y build-essential libtool autotools-dev automake pkg-config bsdmainutils python3 python3-pip

# 安装 Bitcoin Core 核心依赖
sudo apt install -y libssl-dev libevent-dev libboost-all-dev

# 安装 ORIM 特定依赖（关键）
# libzmq3-dev: 用于 C++/Python 进程间通信
# libsqlite3-dev: 用于消息队列存储
sudo apt install -y libzmq3-dev libsqlite3-dev
```

### macOS 系统

需要先安装 Xcode 命令行工具和 Homebrew。

```bash
# Bitcoin Core 基础依赖
brew install automake libtool boost pkg-config libevent

# ORIM 特定依赖（关键）
brew install zeromq sqlite
```

### 依赖版本要求

  - **ZeroMQ**: 4.3.0+ (必需)
  - **Boost**: 1.73.0+
  - **OpenSSL**: 1.1.1+
  - **Python**: 3.8+

-----

## 2\. Python环境配置

ORIM 算法引擎使用 Python 3 实现，推荐使用 Conda 管理环境。

### 2.1 安装 Miniconda

**Linux**:

```bash
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh
```

**macOS (Apple Silicon)**:

```bash
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-arm64.sh
bash Miniconda3-latest-MacOSX-arm64.sh
```

### 2.2 创建 ORIM 专用环境

```bash
# 创建并激活环境
conda create -n orim_env python=3.9 -y
conda activate orim_env

# 安装 Python 依赖
pip install pyzmq
```

**验证环境**:

```bash
python3 -c "import zmq; print(f'PyZMQ version: {zmq.zmq_version()}')"
# 预期输出: PyZMQ version: 4.3.5 (或更高)
```

-----

## 3\. Bitcoin Core编译

### 3.1 获取源代码

```bash
# 进入项目目录
cd /path/to/bitcoin
```

### 3.2 配置构建选项（关键步骤）

**必须启用 ZeroMQ 支持**：

```bash
# 生成配置脚本
./autogen.sh

# 配置构建选项
./configure \
    --with-zmq \
    --with-incompatible-bdb \
    --without-gui \
    --disable-tests \
    --disable-bench
```

**关键检查**:
配置完成后，检查输出中是否包含 `with zmq = yes`。如果显示 `no`，请检查 `libzmq3-dev` 是否已安装。

### 3.3 编译

```bash
# 使用多核并行编译
make -j$(nproc)  # Linux
make -j$(sysctl -n hw.ncpu)  # macOS
```

编译完成后，会在 `src/` 目录下生成 `bitcoind` 和 `bitcoin-cli` 可执行文件。

-----

## 4\. 安装验证

### 4.1 验证 Bitcoin Core

```bash
# 检查是否支持 -enableorim 参数
./src/bitcoind --help | grep -i orim
# 预期输出:
#   -enableorim
#          Enable ORIM covert channel functionality (default: 0)
```

### 4.2 验证 Python 环境

```bash
# 激活环境
conda activate orim_env

# 测试 ORIM 服务器导入
python3 -c "import zmq, json, sqlite3, hashlib, hmac; print('✓ Imports OK')"
```

### 4.3 集成验证（一键测试）

使用项目提供的集成测试脚本进行全流程验证：

```bash
# 确保在项目根目录
bash test_orim_integration.sh
```

**预期结果**:
脚本将自动启动服务器和节点，发送测试消息，并最终输出：

```
✓ SUCCESS! Message received correctly!
```

-----

**下一步骤**:
环境验证无误后，请参考后续文档学习如何配置和使用 ORIM 系统。