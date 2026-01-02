#!/usr/bin/env python3
"""
ORIM Covert Channel Server (Final Edition)
Features:
- Protocol Framing (Magic + CID + CRC)
- Automatic Padding for Capacity Matching
- Bit-wise Sliding Window Decoding
- Debug Logging
"""

import zmq
import json
import hashlib
import hmac
import sqlite3
import sys
import os
import logging
from math import factorial
from typing import List, Tuple, Dict, Optional
from datetime import datetime

# === 引入协议封装 ===
# 直接从 orim_engine 包导入
from protocol import ORIMProtocol

# 配置日志 (这是 Server 运行日志)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('orim_server.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ==========================================
# 🔬 Debug Logger for Binary Tracing (Sender Side)
# ==========================================
debug_logger = logging.getLogger('sender_debug')
debug_logger.setLevel(logging.DEBUG)
# Calculate absolute path to storage directory
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
storage_dir = os.path.join(project_root, 'storage')
os.makedirs(storage_dir, exist_ok=True)
debug_log_path = os.path.join(storage_dir, 'sender_debug.log')

debug_handler = logging.FileHandler(debug_log_path, mode='a')
debug_handler.setLevel(logging.DEBUG)
debug_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
debug_logger.addHandler(debug_handler)
debug_logger.propagate = False

# Force immediate flush after each write
class FlushingHandler(logging.FileHandler):
    def emit(self, record):
        super().emit(record)
        self.flush()

# Replace with flushing handler
debug_logger.removeHandler(debug_handler)
debug_handler_flushing = FlushingHandler(debug_log_path, mode='a')
debug_handler_flushing.setLevel(logging.DEBUG)
debug_handler_flushing.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
debug_logger.addHandler(debug_handler_flushing)

logger.info(f"Debug logger initialized: {debug_log_path}")

class ORIMServer:
    def __init__(self, zmq_endpoint: str, prf_key: bytes, db_path: str):
        self.zmq_endpoint = zmq_endpoint
        self.prf_key = prf_key
        self.db_path = db_path
        
        # Init ZMQ
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.bind(zmq_endpoint)
        logger.info(f"ORIM Server listening on {zmq_endpoint}")
        
        self._init_database()
        
        # Stats
        self.stats = {'sent_msgs': 0, 'recv_msgs': 0, 'bits_sent': 0, 'bits_recv': 0}

    def _init_database(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 发送队列
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS outgoing_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT,
                bits TEXT,
                position INTEGER DEFAULT 0,
                completed_at TIMESTAMP NULL
            )
        ''')
        
        # 接收缓冲区
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS incoming_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                peer_id INTEGER,
                bits TEXT,
                received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 解码结果
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS decoded_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT,
                decoded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()

    # ==========================================
    # 核心数学逻辑 (ORIM 算法实现)
    # ==========================================
    def prf(self, hash_hex: str) -> int:
        """PRF: Hash → Integer (HMAC-SHA256 based)"""
        hash_bytes = bytes.fromhex(hash_hex)
        hmac_obj = hmac.new(self.prf_key, hash_bytes, hashlib.sha256)
        # Use full 256-bit output for better distribution
        return int.from_bytes(hmac_obj.digest(), byteorder='big')

    def compute_obfuscated_values(self, hashes: List[str]) -> List[int]:
        """Compute obfuscated values for all hashes using PRF (Algorithm 2, Step 1)"""
        obf_values = [self.prf(h) for h in hashes]
        debug_logger.debug(f"[PRF] Computed {len(obf_values)} obfuscated values")
        return obf_values

    def factorial_number_system(self, rank: int, n: int) -> List[int]:
        lehmer = []
        for i in range(n, 0, -1):
            fact = factorial(i - 1)
            lehmer.append(rank // fact)
            rank %= fact
        return lehmer

    def lehmer_to_permutation(self, lehmer: List[int]) -> List[int]:
        available = list(range(len(lehmer)))
        return [available.pop(c) for c in lehmer]

    def permutation_to_lehmer(self, permutation: List[int]) -> List[int]:
        n = len(permutation)
        lehmer = []
        for i in range(n):
            count = sum(1 for j in range(i + 1, n) if permutation[j] < permutation[i])
            lehmer.append(count)
        return lehmer

    def lehmer_to_rank(self, lehmer: List[int]) -> int:
        n = len(lehmer)
        return sum(c * factorial(n - 1 - i) for i, c in enumerate(lehmer))

    def bits_to_rank(self, bits: str, n: int) -> Tuple[int, int]:
        """
        Complete Binary Tree Variable-Length Encoding (Algorithm 2)
        
        Given n permutations (N = n!), encode bits to rank using:
        - Layer m (Long Code): m bits → rank ∈ [0, T-1]
        - Layer m-1 (Short Code): m-1 bits → rank ∈ [N - 2^(m-1), N-1]
        
        Where:
        - m: layer number such that 2^(m-1) ≤ N ≤ 2^m
        - T: threshold = 2N - 2^m (number of leaf nodes in layer m)
        
        Returns: (rank, consumed_bits)
        Guarantee: rank < N = n! (mathematically proven)
        """
        N = factorial(n)
        
        # Calculate layer m: 2^(m-1) ≤ N ≤ 2^m
        m = 1
        while (1 << m) < N:
            m += 1
        
        # Threshold T = 2N - 2^m
        T = 2 * N - (1 << m)
        
        # Special case: N is exactly a power of 2 (T = 0)
        if T == 0:
            # All codes use m bits
            if len(bits) < m:
                # Pad with zeros
                bits = bits.ljust(m, '0')
            val_m = int(bits[:m], 2)
            debug_logger.debug(f"[ENCODE] n={n} N={N} m={m} T={T} → Layer-m (special): consumed={m} rank={val_m}")
            return val_m, m
        
        # General case: Complete Binary Tree
        # Peek at m bits to decide which layer
        if len(bits) >= m:
            val_m = int(bits[:m], 2)
            
            # Condition A: val_m < T → use Layer m (Long Code)
            if val_m < T:
                debug_logger.debug(f"[ENCODE] n={n} N={N} m={m} T={T} → Layer-m (long): val_m={val_m} consumed={m} rank={val_m}")
                return val_m, m
            
            # Condition B: val_m ≥ T → use Layer m-1 (Short Code)
            else:
                val_m_minus_1 = int(bits[:m-1], 2)
                rank = N - (1 << (m - 1)) + val_m_minus_1
                debug_logger.debug(f"[ENCODE] n={n} N={N} m={m} T={T} → Layer-m-1 (short): val_m={val_m}≥T, val_{m-1}={val_m_minus_1} consumed={m-1} rank={rank}")
                return rank, m - 1
        
        elif len(bits) >= m - 1:
            # Only have m-1 bits, must use Layer m-1
            val_m_minus_1 = int(bits[:m-1], 2)
            rank = N - (1 << (m - 1)) + val_m_minus_1
            debug_logger.debug(f"[ENCODE] n={n} N={N} m={m} T={T} → Layer-m-1 (forced): insufficient bits, val_{m-1}={val_m_minus_1} consumed={m-1} rank={rank}")
            return rank, m - 1
        
        else:
            # Insufficient bits even for m-1, pad and use Layer m-1
            bits_padded = bits.ljust(m - 1, '0')
            val_m_minus_1 = int(bits_padded, 2)
            rank = N - (1 << (m - 1)) + val_m_minus_1
            debug_logger.debug(f"[ENCODE] n={n} N={N} m={m} T={T} → Layer-m-1 (padded): only {len(bits)} bits, padded val_{m-1}={val_m_minus_1} consumed={len(bits)} rank={rank}")
            return rank, len(bits)

    def rank_to_bits(self, rank: int, n: int) -> str:
        """
        Complete Binary Tree Variable-Length Decoding (Inverse of bits_to_rank)
        
        Decode rank to bits using the same layer logic:
        - If rank < T: decode as m-bit value
        - If rank ≥ N - 2^(m-1): decode as m-1-bit value from Layer m-1
        
        Returns: bits string (variable length)
        """
        N = factorial(n)
        
        # Calculate layer m
        m = 1
        while (1 << m) < N:
            m += 1
        
        # Threshold T = 2N - 2^m
        T = 2 * N - (1 << m)
        
        # Special case: N is exactly a power of 2
        if T == 0:
            bits = bin(rank)[2:].zfill(m)
            debug_logger.debug(f"[DECODE] n={n} rank={rank} → Layer-m (special): {bits}")
            return bits
        
        # Determine which layer this rank belongs to
        layer_m_minus_1_start = N - (1 << (m - 1))
        
        if rank < T:
            # Layer m (Long Code): m bits
            bits = bin(rank)[2:].zfill(m)
            debug_logger.debug(f"[DECODE] n={n} rank={rank} < T={T} → Layer-m: {bits}")
            return bits
        else:
            # Layer m-1 (Short Code): m-1 bits
            val_m_minus_1 = rank - layer_m_minus_1_start
            bits = bin(val_m_minus_1)[2:].zfill(m - 1)
            debug_logger.debug(f"[DECODE] n={n} rank={rank} ≥ {layer_m_minus_1_start} → Layer-m-1: val={val_m_minus_1} bits={bits}")
            return bits

    # ==========================================
    # 数据流处理逻辑
    # ==========================================
    
    def get_next_secret_bits(self, n: int) -> Tuple[str, int, int, int]:
        """
        [Sender Logic] Fetch next bits from database with "Check & Consume" strategy
        
        Implements Algorithm 2 "Check & Consume" Step:
        1. Calculate N = n!, m, and threshold T
        2. Peek at next m bits from buffer
        3. Decide consumption:
           - If val_m < T: consume m bits (Layer m)
           - If val_m ≥ T: consume m-1 bits (Layer m-1)
        4. Calculate target_rank according to the layer
        
        Returns: (bits_chunk, msg_id, actual_data_len, target_rank)
        Guarantee: target_rank < N (no overflow possible)
        """
        N = factorial(n)
        
        # Calculate layer m: 2^(m-1) ≤ N ≤ 2^m
        m = 1
        while (1 << m) < N:
            m += 1
        
        # Threshold T = 2N - 2^m
        T = 2 * N - (1 << m)
        
        # Fetch message from database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT id, bits, position FROM outgoing_messages WHERE completed_at IS NULL LIMIT 1')
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            # No message to send, return dummy data
            dummy_bits = "0" * m
            debug_logger.info(f"[CHECK&CONSUME] n={n} N={N} m={m} T={T} → No message, returning {m} dummy zeros")
            return (dummy_bits, -1, 0, 0)
        
        msg_id, full_bits, pos = row
        total_len = len(full_bits)
        remaining = total_len - pos
        
        # === "Check & Consume" Logic (Algorithm 2) ===
        
        # Special case: N is power of 2 (T = 0)
        if T == 0:
            # Always consume m bits
            chunk = full_bits[pos:pos + m]
            if len(chunk) < m:
                chunk = chunk.ljust(m, '0')  # Pad if insufficient
            target_rank = int(chunk, 2)
            actual_data_len = min(remaining, m)
            conn.close()
            debug_logger.info(f"[CHECK&CONSUME] n={n} N={N} m={m} T=0 (power-of-2) → consumed={m} rank={target_rank}")
            return (chunk, msg_id, actual_data_len, target_rank)
        
        # General case: Check m bits to decide
        if remaining >= m:
            # Peek at m bits
            peek_m = full_bits[pos:pos + m]
            val_m = int(peek_m, 2)
            
            # Condition A: val_m < T → use Layer m (Long Code)
            if val_m < T:
                chunk = peek_m
                consumed = m
                target_rank = val_m
                layer = f"Layer-m (long)"
            
            # Condition B: val_m ≥ T → use Layer m-1 (Short Code)
            else:
                chunk = full_bits[pos:pos + m - 1]
                val_m_minus_1 = int(chunk, 2)
                consumed = m - 1
                target_rank = N - (1 << (m - 1)) + val_m_minus_1
                layer = f"Layer-m-1 (short)"
            
            actual_data_len = consumed
            conn.close()
            debug_logger.info(
                f"[CHECK&CONSUME] n={n} N={N} m={m} T={T} → {layer}: "
                f"val_m={val_m if val_m < T else 'N/A'} consumed={consumed} rank={target_rank}"
            )
            return (chunk, msg_id, actual_data_len, target_rank)
        
        elif remaining >= m - 1:
            # Only have m-1 bits, must use Layer m-1
            chunk = full_bits[pos:pos + m - 1]
            val_m_minus_1 = int(chunk, 2)
            consumed = m - 1
            target_rank = N - (1 << (m - 1)) + val_m_minus_1
            actual_data_len = consumed
            conn.close()
            debug_logger.info(
                f"[CHECK&CONSUME] n={n} N={N} m={m} T={T} → Layer-m-1 (forced, insufficient): "
                f"only {remaining} bits, consumed={consumed} rank={target_rank}"
            )
            return (chunk, msg_id, actual_data_len, target_rank)
        
        else:
            # Insufficient bits even for m-1, pad to m-1
            chunk = full_bits[pos:]
            chunk_padded = chunk.ljust(m - 1, '0')
            val_m_minus_1 = int(chunk_padded, 2)
            consumed = len(chunk)
            target_rank = N - (1 << (m - 1)) + val_m_minus_1
            actual_data_len = consumed
            conn.close()
            debug_logger.info(
                f"[CHECK&CONSUME] n={n} N={N} m={m} T={T} → Layer-m-1 (padded): "
                f"only {remaining} bits, padded to {m-1}, consumed={consumed} rank={target_rank}"
            )
            return (chunk_padded, msg_id, actual_data_len, target_rank)

    def store_received_bits(self, peer_id: int, bits: str):
        """
        [接收端逻辑] 存入缓冲区并尝试解码
        包含: 调试日志写入
        """
        # 1. 存入数据库
        conn = sqlite3.connect(self.db_path)
        conn.execute('INSERT INTO incoming_messages (peer_id, bits) VALUES (?, ?)', (peer_id, bits))
        conn.commit()
        conn.close()
        
        # 2. [调试] 写入 received_bits.log
        try:
            log_path = self.db_path.replace('orim.db', 'received_bits.log')
            with open(log_path, "a") as f:
                time_str = datetime.now().strftime("%H:%M:%S")
                f.write(f"[{time_str}] Len={len(bits)}: {bits}\n")
        except Exception as e:
            logger.error(f"Failed to write debug log: {e}")

        # 3. 触发解码
        # (如果你以后启用了独立的 decoder_service.py，可以注释掉下面这就行)
        self._try_decode_messages()

    def _try_decode_messages(self):
        """
        [内部解码器] 全量扫描 + 协议层识别
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 1. 提取所有比特流拼成一个大长串
        cursor.execute('SELECT bits FROM incoming_messages ORDER BY received_at')
        rows = cursor.fetchall()
        full_stream = "".join([row[0] for row in rows])
        
        if not full_stream:
            conn.close()
            return

        # 2. 循环调用协议层扫描
        while True:
            # 使用单比特滑动窗口扫描 (支持自动去Padding，自动纠错位)
            cid, bits_consumed = ORIMProtocol.decode_stream(full_stream)
            
            if cid:
                logger.info(f"🎉 DECODED FILE INDEX: {cid}")
                # 存入解码结果表
                cursor.execute('INSERT INTO decoded_messages (message) VALUES (?)', (cid,))
                conn.commit()
                
                # 剪掉已处理的比特
                full_stream = full_stream[bits_consumed:]
            else:
                # 找不到了，退出
                break
        
        # 3. 残余回收 (Residue Recycling)
        cursor.execute('DELETE FROM incoming_messages')
        
        # 限制残渣大小，防止无限增长
        if len(full_stream) > 4000:
            full_stream = full_stream[-4000:]
            
        if full_stream:
            # 将剩下的比特存回去，作为下次解码的开头
            cursor.execute('INSERT INTO incoming_messages (peer_id, bits) VALUES (-1, ?)', (full_stream,))
            
        conn.commit()
        conn.close()

    # ==========================================
    # C++ 交互接口 (ZMQ Handlers)
    # ==========================================
    
    def handle_send_request(self, request: Dict) -> Dict:
        """处理发送请求：将比特编码进哈希顺序"""
        try:
            hashes = request['hashes']
            n = len(hashes)
            if n < 2: return {'status': 'success', 'reordered_hashes': hashes}
            
            # 1. 计算混淆值并获取自然序
            obf_vals = self.compute_obfuscated_values(hashes)
            # 自然序: 按 PRF 值从小到大的原始索引列表
            natural_order = [i for _, i in sorted((v, i) for i, v in enumerate(obf_vals))]
            
            # 2. 获取比特并计算 target_rank (Algorithm 2: Check & Consume)
            # 新接口直接返回 target_rank，保证 rank < n! (无需再次验证)
            bits, msg_id, actual_data_len, target_rank = self.get_next_secret_bits(n)
            
            # === FIX: 如果没有消息要发送（msg_id=-1），直接返回原始顺序 ===
            if msg_id == -1:
                # 按自然序排列（PRF值从小到大）
                debug_logger.info(f"[SEND] n={n} No message \u2192 Natural order (rank=0)")
                return {'status': 'success', 'reordered_hashes': [hashes[i] for i in natural_order]}
            
            # 3. Log the encoding result
            # target_rank is already calculated by get_next_secret_bits using Algorithm 2
            # Mathematically guaranteed: target_rank < n! (no overflow possible)
            conn_read = sqlite3.connect(self.db_path)
            cursor_read = conn_read.cursor()
            cursor_read.execute('SELECT position FROM outgoing_messages WHERE id = ?', (msg_id,))
            current_pos = cursor_read.fetchone()[0]
            conn_read.close()
            
            # Calculate consumed bits by calling bits_to_rank again (for logging consistency)
            _, consumed = self.bits_to_rank(bits, n)
            
            debug_logger.debug(
                f"[SENDING_SLICE] MsgID={msg_id} Pos={current_pos} "
                f"BitsLen={len(bits)} ActualData={actual_data_len} Consumed={consumed} "
                f"Rank={target_rank} Bits={bits[:50]}{'...' if len(bits) > 50 else ''}"
            )
            
            # 4. 更新数据库发送进度
            # 使用 actual_data_len (实际从数据库消耗的位数)
            # 这与 get_next_secret_bits 返回的 consumed 位数一致
            if msg_id != -1:
                with sqlite3.connect(self.db_path) as conn:
                    # Update position by actual consumed data length
                    conn.execute('UPDATE outgoing_messages SET position = position + ? WHERE id = ?', (actual_data_len, msg_id))
                    
                    # 检查是否发送完毕
                    cursor = conn.execute('SELECT position, length(bits) FROM outgoing_messages WHERE id = ?', (msg_id,))
                    pos, total = cursor.fetchone()
                    if pos >= total:
                        conn.execute('UPDATE outgoing_messages SET completed_at = CURRENT_TIMESTAMP WHERE id = ?', (msg_id,))
                        logger.info(f"✅ Message #{msg_id} transmission completed (Total bits: {total})")
            
            # 5. 生成排列并重排哈希
            try:
                lehmer = self.factorial_number_system(target_rank, n)
                perm = self.lehmer_to_permutation(lehmer)
                final_indices = [natural_order[perm[i]] for i in range(n)]
            except Exception as e:
                logger.error(f"Permutation Error: n={n} rank={target_rank} error={e}")
                debug_logger.error(f"[PERM_ERROR] n={n} rank={target_rank} bits={bits} error={e}")
                # 返回自然序作为备选
                return {'status': 'success', 'reordered_hashes': [hashes[i] for i in natural_order]}
            
            self.stats['sent_msgs'] += 1
            self.stats['bits_sent'] += consumed
            logger.info(f"Sender: Encoded {consumed} bits (Rank={target_rank})")
            
            return {'status': 'success', 'reordered_hashes': [hashes[i] for i in final_indices]}
            
        except Exception as e:
            logger.error(f"Send Error: {e}")
            return {'status': 'error', 'message': str(e)}

    def handle_receive_request(self, request: Dict) -> Dict:
        """处理接收请求：排序 -> 提取比特"""
        try:
            hashes = request['hashes']
            n = len(hashes)
            
            # === CRITICAL FIX: Log single-hash trap ===
            if n < 2: 
                logger.info(f"Receiver: Ignored INV with {n} hash (need >= 2 for permutation)")
                return {'status': 'success'}
            # === End Fix ===
            
            # ... 后面的代码保持不变 ...
            
            # 1. 逆向计算 Rank
            obf_vals = self.compute_obfuscated_values(hashes)
            
            # 还原排列逻辑
            indexed_values = [(v, i) for i, v in enumerate(obf_vals)]
            sorted_indexed = sorted(indexed_values)
            sorted_order = [orig_idx for _, orig_idx in sorted_indexed]
            
            sorted_to_received = {s_idx: pos for pos, s_idx in enumerate(sorted_order)}
            rec_perm = [sorted_to_received[i] for i in range(n)]
            
            lehmer = self.permutation_to_lehmer(rec_perm)
            rank = self.lehmer_to_rank(lehmer)
            
            # 2. 提取比特
            bits = self.rank_to_bits(rank, n)
            
            # 🔬 DEBUG: Log received bits
            debug_logger.debug(f"[RECEIVED_BITS] n={n} Rank={rank} ExtractedLen={len(bits)} Bits={bits}")
            
            # 3. 存入并解码
            self.store_received_bits(request.get('peer_id', 0), bits)
            
            self.stats['recv_msgs'] += 1
            self.stats['bits_recv'] += len(bits)
            logger.info(f"Receiver: Extracted {len(bits)} bits (Rank={rank})")
            
            return {'status': 'success'}
            
        except Exception as e:
            logger.error(f"Recv Error: {e}")
            return {'status': 'error', 'message': str(e)}

    def run(self):
        logger.info("Service Loop Started.")
        while True:
            try:
                msg = self.socket.recv_string()
                req = json.loads(msg)
                resp = self.handle_send_request(req) if req['direction'] == 'send' else self.handle_receive_request(req)
                self.socket.send_string(json.dumps(resp))
            except KeyboardInterrupt:
                logger.info("Server Stopped.")
                break
            except Exception as e:
                logger.error(f"Loop Error: {e}")
                self.socket.send_string(json.dumps({'status': 'error'}))

# ==========================================
# 工具函数：添加消息到队列 (CLI入口)
# ==========================================
def add_secret_message(db_path: str, cid_string: str):
    """
    将 IPFS CID 封装为协议帧并存入数据库
    """
    try:
        # 使用协议打包 (Magic + CID + CRC)
        bits = ORIMProtocol.pack_cid(cid_string)
        
        # 🔬 TRACE STEP 1: Log full binary string after CID conversion
        debug_logger.debug(f"[NEW_MSG] CID={cid_string} TotalLen={len(bits)} Bits={bits}")
        
        conn = sqlite3.connect(db_path)
        conn.execute('INSERT INTO outgoing_messages (message, bits) VALUES (?, ?)', (cid_string, bits))
        msg_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        conn.commit()
        conn.close()
        
        # 🔬 TRACE STEP 2: Confirm database insertion
        debug_logger.debug(f"[DB_INSERTED] MsgID={msg_id} CID={cid_string} StoredBits={len(bits)}")
        
        print(f"✅ Message Queued: {cid_string} (Encoded to {len(bits)} bits)")
    except ValueError as e:
        print(f"❌ Error adding message: {e}")

if __name__ == '__main__':
    import argparse
    import os
    
    # 1. 算出绝对路径 (不管你在哪启动，路径永远固定)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # 假设 storage 在 orim_server.py 的上一级目录的 storage 文件夹里
    project_root = os.path.dirname(current_dir) 
    db_path_absolute = os.path.join(project_root, 'storage', 'orim.db')
    
    # 打印出来检查
    print(f"🔧 [DEBUG] 强制数据库绝对路径: {db_path_absolute}")

    parser = argparse.ArgumentParser()
    # 重点：把默认值改为这个绝对路径变量
    parser.add_argument('--db', default=db_path_absolute, help='Path to SQLite database')
    parser.add_argument('--add-message', help='Add IPFS CID to queue')
    args = parser.parse_args()
    
    if args.add_message:
        add_secret_message(args.db, args.add_message)
    else:
        # 启动时使用 args.db
        ORIMServer('tcp://*:5555', b'secret', args.db).run()