#!/usr/bin/env python3
"""
测试 Complete Binary Tree 编码/解码逻辑
验证 bits_to_rank 和 rank_to_bits 是否互为逆运算
"""

import sys
import os
from math import factorial

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'orim_engine'))
from orim_server import ORIMServer

def test_round_trip(n, test_bits):
    """测试 bits → rank → bits 的往返转换"""
    server = ORIMServer('tcp://*:9999', b'test', ':memory:')
    
    print(f"\n{'='*70}")
    print(f"测试 n={n}, bits='{test_bits}' (长度={len(test_bits)})")
    print(f"{'='*70}")
    
    n_fact = factorial(n)
    m = 1
    while (1 << m) < n_fact:
        m += 1
    threshold = (1 << m) - n_fact
    
    print(f"n! = {n_fact}")
    print(f"m = {m} (2^{m-1}={1<<(m-1)} < {n_fact} ≤ 2^{m}={1<<m})")
    print(f"threshold = 2^{m} - n! = {threshold}")
    print(f"预期: ranks [0, {threshold-1}] 编码 {m} 位, ranks [{threshold}, {n_fact-1}] 编码 {m-1} 位")
    
    # 编码
    rank, consumed = server.bits_to_rank(test_bits, n)
    print(f"\n[编码] bits → rank")
    print(f"  输入: '{test_bits}' ({len(test_bits)} bits)")
    print(f"  输出: rank={rank}, consumed={consumed}")
    print(f"  使用位数: {consumed} bits")
    print(f"  实际使用的 bits: '{test_bits[:consumed]}'")
    
    # 验证 rank 是否合法
    if rank >= n_fact:
        print(f"  ⚠️ 警告: rank={rank} >= n!={n_fact}，超出范围！")
        return False
    
    # 解码
    decoded_bits = server.rank_to_bits(rank, n)
    print(f"\n[解码] rank → bits")
    print(f"  输入: rank={rank}")
    print(f"  输出: '{decoded_bits}' ({len(decoded_bits)} bits)")
    
    # 比较
    expected = test_bits[:consumed]
    print(f"\n[验证]")
    print(f"  原始 bits (前{consumed}位): '{expected}'")
    print(f"  解码 bits:            '{decoded_bits}'")
    
    if decoded_bits == expected:
        print(f"  ✅ 成功: 编码/解码一致")
        return True
    else:
        print(f"  ❌ 失败: 编码/解码不一致")
        print(f"  差异: 原始={expected}, 解码={decoded_bits}")
        return False

def test_all_ranks(n):
    """测试所有可能的 rank 值"""
    server = ORIMServer('tcp://*:9999', b'test', ':memory:')
    n_fact = factorial(n)
    
    print(f"\n{'='*70}")
    print(f"穷举测试: n={n}, 测试所有 ranks [0, {n_fact-1}]")
    print(f"{'='*70}")
    
    m = 1
    while (1 << m) < n_fact:
        m += 1
    threshold = (1 << m) - n_fact
    
    failures = []
    
    for rank in range(n_fact):
        # 解码
        bits = server.rank_to_bits(rank, n)
        
        # 编码回去
        decoded_rank, consumed = server.bits_to_rank(bits, n)
        
        if decoded_rank != rank:
            failures.append((rank, bits, decoded_rank, consumed))
            print(f"❌ rank={rank} → bits='{bits}' → rank={decoded_rank} (consumed={consumed})")
    
    if not failures:
        print(f"✅ 所有 {n_fact} 个 rank 值都通过测试")
        return True
    else:
        print(f"\n❌ 失败 {len(failures)}/{n_fact} 个测试:")
        for rank, bits, decoded_rank, consumed in failures[:10]:  # 只显示前10个
            print(f"  rank={rank} → '{bits}' ({len(bits)} bits) → rank={decoded_rank} (consumed={consumed})")
        return False

if __name__ == "__main__":
    print("="*70)
    print("Complete Binary Tree 编码/解码测试")
    print("="*70)
    
    # 测试案例1: n=5 (5! = 120)
    test_round_trip(5, "1010101")
    test_round_trip(5, "0000000")
    test_round_trip(5, "1111111")
    
    # 测试案例2: n=3 (3! = 6)
    test_round_trip(3, "101")
    test_round_trip(3, "000")
    test_round_trip(3, "111")
    
    # 测试案例3: n=10 (10! = 3628800)
    test_round_trip(10, "10101010101010101010101")
    
    # 穷举测试
    print("\n\n" + "="*70)
    print("穷举测试")
    print("="*70)
    test_all_ranks(3)
    test_all_ranks(5)
    test_all_ranks(7)
    
    print("\n" + "="*70)
    print("测试完成")
    print("="*70)
