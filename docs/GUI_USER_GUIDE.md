# ORIM 端到端文件传输系统 - GUI 使用指南

## 🎯 系统概述

这是一个基于 IPFS + 区块链隐蔽信道的端到端加密文件传输系统。

**特点：**
- 🔐 文件端到端加密（AES-256）
- 🌐 IPFS 分布式存储
- 🔗 区块链隐蔽信道传输
- 👥 Alice-Bob 双窗口演示界面

---

## 🚀 快速启动

### 1. 启动 IPFS Daemon（如未运行）
```bash
nohup ipfs daemon > /tmp/ipfs_daemon.log 2>&1 &
```

### 2. 启动 GUI
```bash
./start_gui.sh
```

或者直接运行：
```bash
cd orim_engine
source ~/miniconda3/bin/activate orim_env
python3 orim_gui.py
```

---

## 📖 使用流程

### 界面布局
```
┌────────────────────────────────────────────────────────────────┐
│                    系统状态 (顶部)                                │
├──────────────────────────┬─────────────────────────────────────┤
│   👩 Alice - 发送方       │      👨 Bob - 接收方                 │
│                          │                                     │
│  📁 选择文件              │   接收到的文件列表                    │
│  🚀 加密并上传            │   ┌─────────────────────┐           │
│                          │   │ CID | 时间 | 状态    │           │
│  已发送文件列表            │   └─────────────────────┘           │
│  ┌──────────────────┐    │                                     │
│  │ 文件名 | CID...   │    │   ⬇️ 下载选中文件                    │
│  └──────────────────┘    │   🔄 刷新列表                        │
│                          │                                     │
│  操作日志                 │   操作日志                           │
└──────────────────────────┴─────────────────────────────────────┘
```

---

## 🎬 完整演示步骤

### Alice 发送文件

1. **选择文件**
   - 点击左侧 `📁 选择文件` 按钮
   - 选择要发送的文件（例如：`/tmp/alice_secret_message.txt`）
   - 文件名和大小会显示在选择框中

2. **加密并上传**
   - 点击 `🚀 加密并上传` 按钮
   - 系统自动执行：
     * 使用 Fernet (AES-256) 加密文件
     * 上传加密文件到 IPFS
     * 获取 CID (Content Identifier)
     * 将 CID 打包为 392 bits (Magic + CID + CRC)
     * 插入到 `outgoing_messages` 表，等待传输

3. **查看发送状态**
   - 已发送文件列表显示：
     * 文件名
     * CID（双击可复制）
     * 文件大小
     * 发送时间
   - 操作日志显示详细过程

### Bob 接收文件

1. **等待接收**
   - GUI 后台自动监控 `decoded_messages` 表
   - 当 `decoder_service.py` 从区块链解码出 CID 后：
     * 自动出现在 Bob 的接收列表
     * 播放提示音
     * 状态显示 `⏳ 待下载`

2. **下载文件**
   - 选中接收到的 CID
   - 点击 `⬇️ 下载选中文件` 按钮
   - 系统自动执行：
     * 从 IPFS 下载加密文件
     * 使用存储的密钥解密
     * 保存到 `storage/downloads/` 目录
     * 状态更新为 `✅ 已下载`

3. **查看下载结果**
   - 操作日志显示保存路径
   - 弹窗显示完整路径

---

## 🧪 测试示例

### 准备测试文件
```bash
cat > /tmp/alice_secret_message.txt << 'EOF'
🔐 机密文件 - Alice to Bob

这是通过区块链隐蔽信道传输的加密文件。
文件内容端到端加密，只有 Bob 能解密。

测试时间: 2025-12-18
EOF
```

### 模拟完整流程

#### 方案 A：手动模拟（不启动区块链）
1. Alice 上传文件，获得 CID
2. 手动将 CID 插入到 Bob 的 `decoded_messages` 表：
   ```bash
   sqlite3 storage/orim.db "INSERT INTO decoded_messages (message, decoded_at) VALUES ('QmXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX', datetime('now'))"
   ```
3. Bob 的 GUI 会自动检测到新 CID
4. Bob 点击下载

#### 方案 B：完整系统测试
1. 启动完整 ORIM 系统：`./start_demo.sh`
2. Alice 在 GUI 上传文件
3. 等待 `traffic_bot.py` 通过区块链传输（约 10-60 秒）
4. Bob 在 GUI 接收并下载

---

## 🔍 调试信息

### 日志文件位置
- **IPFS Daemon**: `/tmp/ipfs_daemon.log`
- **发送调试**: `storage/sender_debug.log`
- **ORIM Server**: `storage/orim_server.log`
- **Decoder**: `storage/decoder.log`
- **Traffic Bot**: `storage/traffic_bot.log`

### 数据库表结构
```sql
-- 发送队列
SELECT * FROM outgoing_messages ORDER BY id DESC LIMIT 5;

-- 接收队列
SELECT * FROM decoded_messages ORDER BY id DESC LIMIT 5;

-- 加密密钥（JSON文件）
cat storage/crypto_keys.json
```

### 常见问题

**Q1: GUI 显示 "IPFS download failed: 500"**
- 检查 IPFS daemon 是否运行：`ps aux | grep "ipfs daemon"`
- 重启 IPFS：`ipfs shutdown && nohup ipfs daemon > /tmp/ipfs_daemon.log 2>&1 &`

**Q2: Bob 收不到文件**
- 检查是否启动了 `decoder_service.py`
- 查看 `decoded_messages` 表是否有记录
- 检查 `storage/decoder.log` 日志

**Q3: 下载后文件无法打开**
- 确认 Alice 和 Bob 使用相同的密钥存储
- 检查 `storage/crypto_keys.json` 是否包含该 CID 的密钥
- 验证文件完整性（检查 CRC）

**Q4: 加密密钥如何共享？**
- 当前实现：密钥存储在本地 `crypto_keys.json`
- 生产环境：需要实现密钥交换协议（如 Diffie-Hellman）
- 测试环境：可以手动复制 `crypto_keys.json` 到 Bob 的机器

---

## 🎨 界面特性

### Alice 侧（左）
- ✅ 拖拽/选择文件
- ✅ 显示文件信息（名称、大小）
- ✅ 一键加密上传
- ✅ 历史发送记录
- ✅ 双击复制 CID
- ✅ 实时操作日志

### Bob 侧（右）
- ✅ 自动检测新 CID
- ✅ 显示接收时间
- ✅ 下载状态跟踪
- ✅ 一键下载解密
- ✅ 手动刷新列表
- ✅ 实时操作日志

---

## 🔐 安全特性

1. **端到端加密**
   - 文件在 Alice 端加密
   - IPFS 存储加密数据
   - Bob 端解密还原

2. **隐蔽传输**
   - CID 通过区块链 nonce 值传输
   - 外部观察者无法识别文件传输行为
   - 完全符合区块链协议规范

3. **完整性校验**
   - CRC-8 校验和
   - Fernet 内置 HMAC 认证
   - 防止篡改和中间人攻击

---

## 📊 性能指标

- **加密速度**: ~1-10 MB/s
- **IPFS 上传**: 取决于网络带宽
- **区块链传输**: ~10-60 秒/CID（取决于出块速度）
- **CID 大小**: 392 bits = 49 bytes
- **支持文件大小**: 无限制（受 IPFS 限制）

---

## 🚧 未来改进

- [ ] 批量文件传输
- [ ] 密钥交换协议
- [ ] 文件元数据传输（文件名、类型）
- [ ] 传输进度条
- [ ] 下载队列管理
- [ ] 自动重试机制
- [ ] 传输统计图表

---

## 📞 技术支持

如有问题，请查看：
1. 项目文档：`docs/ORIM_README.md`
2. 实现报告：`docs/ORIM_IMPLEMENTATION_REPORT_PART2.md`
3. 日志文件：`storage/*.log`
