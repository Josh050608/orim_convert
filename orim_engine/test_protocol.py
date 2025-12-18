#!/usr/bin/env python3
import sys
import os
import random
import binascii

# 尝试导入 ORIMProtocol
# 假设你的目录结构是 orim_engine/core/protocol.py
try:
    from core.protocol import ORIMProtocol
    print("✅ 成功导入 ORIMProtocol")
except ImportError:
    # 如果你在 core 目录下直接运行，尝试直接导入
    try:
        from protocol import ORIMProtocol
        print("✅ 成功导入 ORIMProtocol (本地模式)")
    except ImportError:
        print("❌ 错误: 找不到 protocol.py，请检查文件位置")
        sys.exit(1)

# 颜色定义
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
NC = '\033[0m'

def run_test(name, func):
    """测试运行器帮助函数"""
    print(f"\n🔹 正在运行测试: {name}...")
    try:
        func()
        print(f"{GREEN}✓ 测试通过{NC}")
    except AssertionError as e:
        print(f"{RED}✗ 测试失败: {e}{NC}")
    except Exception as e:
        print(f"{RED}✗ 发生意外错误: {e}{NC}")

def get_dummy_cid():
    """生成一个合法的 46 字节测试 CID"""
    # IPFS v0 CID 总是以 Qm 开头 (2字节)
    # 我们还需要 44 个字符来凑够 46 字节
    prefix = "Qm"
    # 原来的 padding 少了2位，现在补齐
    padding = "TestHash123456789012345678901234567890123456" 
    
    # 验证一下长度
    cid = prefix + padding
    assert len(cid) == 46, f"测试数据生成长度错误: {len(cid)}"
    return cid

# ==========================================
# 测试用例
# ==========================================

def test_valid_pack_unpack():
    """测试 1: 正常的打包与解包流程"""
    cid = get_dummy_cid()
    print(f"   原始 CID: {cid} (长度: {len(cid)})")
    
    # 1. 打包
    bits = ORIMProtocol.pack_cid(cid)
    expected_bits_len = 49 * 8 # 49 bytes * 8 bits
    assert len(bits) == expected_bits_len, f"打包后的比特长度错误, 期望 {expected_bits_len}, 实际 {len(bits)}"
    
    # 2. 解包
    decoded_cid, consumed = ORIMProtocol.decode_stream(bits)
    
    assert decoded_cid == cid, f"解码内容不匹配! \n期望: {cid}\n实际: {decoded_cid}"
    assert consumed == expected_bits_len, "消耗比特数计算错误"

def test_invalid_cid_format():
    """测试 2: 非法 CID 格式校验"""
    # 情况 A: 长度不对
    short_cid = "QmTooShort"
    try:
        ORIMProtocol.pack_cid(short_cid)
        raise AssertionError("应该拦截长度不足的 CID")
    except ValueError as e:
        print(f"   (预期内错误) 拦截短 CID 成功: {e}")

    # 情况 B: 前缀不对
    wrong_prefix = "Xy" + "a" * 44
    try:
        ORIMProtocol.pack_cid(wrong_prefix)
        raise AssertionError("应该拦截非 Qm 开头的 CID")
    except ValueError as e:
        print(f"   (预期内错误) 拦截错误前缀成功: {e}")

def test_noise_resilience():
    """测试 3: 抗噪扫描 (Magic Header 查找)"""
    cid = get_dummy_cid()
    valid_bits = ORIMProtocol.pack_cid(cid)
    
    # 制造 100 位的随机噪音
    noise = "".join(random.choice('01') for _ in range(100))
    
    # 将噪音放在有效数据前面
    dirty_stream = noise + valid_bits
    
    print(f"   输入流: [噪音 {len(noise)} bits] + [有效数据 {len(valid_bits)} bits]")
    
    decoded_cid, consumed = ORIMProtocol.decode_stream(dirty_stream)
    
    assert decoded_cid == cid, "在噪音中未能找到有效 CID"
    
    # 关键检查: consumed 应该等于 噪音长度 + 有效帧长度 吗？
    # 不一定，decode_stream 的逻辑是找到帧尾。
    # 根据代码逻辑: consumed = (idx + FRAME_LEN) * 8
    # idx 是 Magic 所在的字节索引。
    # 噪音长度不一定是 8 的倍数，这会测试字节对齐逻辑。
    
    # 如果 protocol 是按字节扫描的 (byte-aligned)，
    # 我们的噪音如果是 100 bits (12.5 bytes)，可能会导致错位。
    # 当前简化的 Protocol 实现是按 8 位切分的 (bytes)。
    # 如果 noise 不是 8 的倍数，valid_bits 就会发生位移 (Bit Shift)，
    # 简单的按字节扫描会失败。这是预期行为，因为 TCP/IP 或文件传输通常是字节对齐的。
    # 为了测试通过，我们让噪音是 8 的倍数。
    
    aligned_noise = "10101010" * 5 # 40 bits noise
    dirty_stream_aligned = aligned_noise + valid_bits
    
    decoded_cid_2, consumed_2 = ORIMProtocol.decode_stream(dirty_stream_aligned)
    assert decoded_cid_2 == cid, "字节对齐的噪音干扰了解码"
    assert consumed_2 == len(aligned_noise) + len(valid_bits), "消耗长度计算错误"

def test_crc_check():
    """测试 4: CRC 校验 (模拟比特翻转)"""
    cid = get_dummy_cid()
    bits = list(ORIMProtocol.pack_cid(cid))
    
    # 篡改数据：翻转 Payload 中的某一位
    # 前 16 位是 Magic，第 17 位开始是 Payload
    flip_index = 200 
    original_bit = bits[flip_index]
    bits[flip_index] = '0' if original_bit == '1' else '1'
    corrupted_bits = "".join(bits)
    
    print(f"   篡改第 {flip_index} 位比特")
    
    result, _ = ORIMProtocol.decode_stream(corrupted_bits)
    
    assert result is None, "CRC 校验失败！损坏的数据被当成了有效数据！"

def test_multiple_frames():
    """测试 5: 粘包处理 (连续两个帧)"""
    cid1 = get_dummy_cid()
    cid2 = list(cid1)
    cid2[-1] = 'X' # 稍微改一下
    cid2 = "".join(cid2)
    
    bits1 = ORIMProtocol.pack_cid(cid1)
    bits2 = ORIMProtocol.pack_cid(cid2)
    
    stream = bits1 + bits2
    
    # 解码第一个
    res1, consumed1 = ORIMProtocol.decode_stream(stream)
    assert res1 == cid1
    
    # 模拟“滑动窗口”：剪掉已消费的
    remaining_stream = stream[consumed1:]
    
    # 解码第二个
    res2, consumed2 = ORIMProtocol.decode_stream(remaining_stream)
    assert res2 == cid2

if __name__ == "__main__":
    print(f"{YELLOW}========================================{NC}")
    print(f"{YELLOW}   ORIM Protocol 单元测试脚本           {NC}")
    print(f"{YELLOW}========================================{NC}")
    
    run_test("正常打包解包", test_valid_pack_unpack)
    run_test("非法格式校验", test_invalid_cid_format)
    run_test("抗噪能力 (Magic Search)", test_noise_resilience)
    run_test("CRC 数据完整性校验", test_crc_check)
    run_test("多帧连续解码 (粘包)", test_multiple_frames)
    
    print(f"\n{YELLOW}========================================{NC}")
    print(f"{GREEN}所有测试完成!{NC}")