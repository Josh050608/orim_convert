#!/usr/bin/env python3
"""测试 sender_debug.log 是否能正常写入"""

import sys
import os

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'orim_engine'))

# 导入 orim_server 会初始化 debug_logger
from orim_server import debug_logger, add_secret_message

print("=" * 70)
print("测试 Debug Logger 写入")
print("=" * 70)

# 测试1: 直接写入
print("\n[测试1] 直接使用 debug_logger 写入...")
debug_logger.debug("[TEST] This is a test message")
debug_logger.debug("[TEST] Binary: 1010101010101010")
print("✓ 直接写入完成")

# 测试2: 通过 add_secret_message 写入
print("\n[测试2] 通过 add_secret_message 写入...")
project_root = os.path.dirname(os.path.dirname(__file__))
db_path = os.path.join(project_root, 'storage', 'test_orim.db')

try:
    test_cid = "QmYwAPJzv5CZsnAzt8auVZRnrU7V5B3x2mE3Dwn"
    add_secret_message(db_path, test_cid)
    print("✓ add_secret_message 调用完成")
except Exception as e:
    print(f"✗ 错误: {e}")

# 检查日志文件
log_path = os.path.join(project_root, 'storage', 'sender_debug.log')
print(f"\n[检查] 日志文件: {log_path}")

if os.path.exists(log_path):
    with open(log_path, 'r') as f:
        content = f.read()
    print(f"[检查] 文件大小: {len(content)} 字节")
    print(f"[检查] 文件内容:\n{content[-500:]}")  # 显示最后500字符
else:
    print("[检查] ✗ 日志文件不存在！")

print("\n" + "=" * 70)
