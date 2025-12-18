#!/usr/bin/env python3
"""
ORIM 端到端测试脚本（不依赖区块链）
直接测试文件加密、上传、下载、解密流程
"""

import sys
import os
import time
import sqlite3

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'orim_engine'))

from file_sender import ORIMFileSender
from file_receiver import ORIMFileReceiver

def main():
    print("=" * 60)
    print("🧪 ORIM 端到端文件传输测试")
    print("=" * 60)
    print()
    
    # 配置
    project_root = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(project_root, 'storage', 'orim.db')
    test_file = '/tmp/alice_secret_message.txt'
    
    # 检查测试文件
    if not os.path.exists(test_file):
        print(f"❌ 测试文件不存在: {test_file}")
        print("正在创建测试文件...")
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("""🔐 机密文件 - Alice to Bob

这是通过 ORIM 隐蔽信道传输的测试文件。

内容：
- 端到端加密
- IPFS 存储
- 区块链隐蔽传输

测试时间: 2025-12-18
状态: 测试成功 ✅
""")
        print(f"✅ 测试文件已创建: {test_file}")
    
    file_size = os.path.getsize(test_file)
    print(f"📄 测试文件: {test_file}")
    print(f"📏 文件大小: {file_size} bytes")
    print()
    
    # === Alice 发送 ===
    print("👩 Alice: 发送文件")
    print("-" * 60)
    
    sender = ORIMFileSender(db_path)
    
    print("🔐 1. 加密文件...")
    print("📤 2. 上传到 IPFS...")
    print("📝 3. 将 CID 加入发送队列...")
    
    try:
        cid, key_alias = sender.send_file(test_file)
        print(f"✅ 发送成功！")
        print(f"   CID: {cid}")
        print(f"   密钥别名: {key_alias}")
        print()
    except Exception as e:
        print(f"❌ 发送失败: {e}")
        return 1
    
    # === 模拟区块链传输 ===
    print("🔗 区块链传输")
    print("-" * 60)
    print("⏳ 模拟 CID 通过区块链传输...")
    print("   (实际系统中，这一步由 traffic_bot.py 和 decoder_service.py 完成)")
    
    # 直接将 CID 插入到 decoded_messages 表（模拟解码）
    conn = sqlite3.connect(db_path)
    conn.execute(
        'INSERT INTO decoded_messages (message, decoded_at) VALUES (?, datetime("now"))',
        (cid,)
    )
    conn.commit()
    conn.close()
    
    print(f"✅ CID 已传输（模拟）")
    print()
    
    # === Bob 接收 ===
    print("👨 Bob: 接收文件")
    print("-" * 60)
    
    receiver = ORIMFileReceiver(db_path)
    
    print("📥 1. 从 decoded_messages 表读取 CID...")
    received_cids = receiver.get_received_cids()
    
    if cid not in received_cids:
        print(f"❌ 未找到 CID: {cid}")
        return 1
    
    print(f"✅ 找到 CID: {cid}")
    print()
    
    print("⬇️  2. 从 IPFS 下载文件...")
    print("🔓 3. 解密文件...")
    
    try:
        output_filename = f"test_received_{int(time.time())}.txt"
        output_path = receiver.download_file(cid, output_filename)
        print(f"✅ 接收成功！")
        print(f"   保存位置: {output_path}")
        print()
    except Exception as e:
        print(f"❌ 接收失败: {e}")
        return 1
    
    # === 验证文件内容 ===
    print("🔍 验证文件完整性")
    print("-" * 60)
    
    with open(test_file, 'rb') as f:
        original_content = f.read()
    
    with open(output_path, 'rb') as f:
        received_content = f.read()
    
    if original_content == received_content:
        print("✅ 文件内容完全一致！")
        print(f"   原始文件: {len(original_content)} bytes")
        print(f"   接收文件: {len(received_content)} bytes")
        print()
        
        # 显示部分内容
        print("📄 文件内容预览:")
        print("-" * 60)
        preview = received_content.decode('utf-8')[:200]
        print(preview)
        if len(received_content) > 200:
            print("...")
        print()
    else:
        print("❌ 文件内容不一致！")
        print(f"   原始文件: {len(original_content)} bytes")
        print(f"   接收文件: {len(received_content)} bytes")
        return 1
    
    # === 测试总结 ===
    print("=" * 60)
    print("🎉 端到端测试完成")
    print("=" * 60)
    print()
    print("测试流程:")
    print("  ✅ Alice: 加密文件 → 上传 IPFS → 获得 CID")
    print("  ✅ 传输: CID 通过隐蔽信道传输（模拟）")
    print("  ✅ Bob: 接收 CID → 下载文件 → 解密文件")
    print("  ✅ 验证: 文件内容完全一致")
    print()
    print("💡 下一步:")
    print("  1. 运行 ./demo_gui.sh 启动图形界面")
    print("  2. 运行 ./start_demo.sh 启动完整系统（含区块链）")
    print()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
