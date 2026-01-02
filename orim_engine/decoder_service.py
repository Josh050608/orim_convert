#!/usr/bin/env python3
"""
ORIM 独立解码服务 (Incremental Decoder Service)
功能: 增量读取接收到的比特流，流式解码 IPFS 索引，解决全量扫描的性能问题。
"""

import sqlite3
import time
import sys
import logging
import os

# 引入协议层
from protocol import ORIMProtocol

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [DECODER] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('../storage/decoder.log') # 独立日志
    ]
)
logger = logging.getLogger(__name__)

class ORIMDecoderService:
    def __init__(self, db_path="../storage/orim.db"):
        self.db_path = db_path
        self.buffer = ""  # 内存中的比特流缓冲区
        
        # 初始化状态表 (用来记录读到哪了)
        self._init_state_table()

    def _init_state_table(self):
        """创建一个表专门记录解码进度"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS decoder_state (
                key TEXT PRIMARY KEY,
                value INTEGER
            )
        ''')
        # 如果没有记录，初始化为 0
        cursor.execute('INSERT OR IGNORE INTO decoder_state (key, value) VALUES ("last_processed_id", 0)')
        conn.commit()
        conn.close()

    def get_last_id(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM decoder_state WHERE key="last_processed_id"')
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else 0

    def update_last_id(self, last_id):
        conn = sqlite3.connect(self.db_path)
        conn.execute('UPDATE decoder_state SET value=? WHERE key="last_processed_id"', (last_id,))
        conn.commit()
        conn.close()

    def save_decoded_message(self, message):
        """保存解码出的 IPFS 索引"""
        conn = sqlite3.connect(self.db_path)
        conn.execute('INSERT INTO decoded_messages (message) VALUES (?)', (message,))
        conn.commit()
        conn.close()
        logger.info(f"🎉 成功解码新消息: {message}")
        
        # 这里可以加钩子: 自动调用 IPFS 下载
        # os.system(f"python3 handlers/ipfs_handler.py download {message} &")

    def run(self):
        logger.info(f"解码服务启动，监控数据库: {self.db_path}")
        
        while True:
            try:
                # 1. 获取上次处理到的 ID
                last_id = self.get_last_id()
                
                # 2. 读取比这个 ID 更大的新数据
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute('SELECT id, bits FROM incoming_messages WHERE id > ? ORDER BY id ASC', (last_id,))
                rows = cursor.fetchall()
                conn.close()

                if not rows:
                    # 没有新数据，休息一下避免空转 CPU
                    time.sleep(1) 
                    continue

                # 3. 拼接到内存缓冲区
                new_bits_count = 0
                max_id_in_batch = last_id
                
                for row_id, bits in rows:
                    # 过滤掉回收的残渣 (id=-1)，因为我们现在自己在内存里维护残渣
                    if row_id == -1: 
                        continue
                        
                    self.buffer += bits
                    new_bits_count += len(bits)
                    max_id_in_batch = max(max_id_in_batch, row_id)

                logger.info(f"读取到 {len(rows)} 条新记录 ({new_bits_count} bits). 缓冲区总长: {len(self.buffer)}")

                # 4. 扫描解码 (流式处理)
                while True:
                    # 调用之前的协议层逻辑
                    cid, consumed = ORIMProtocol.decode_stream(self.buffer)
                    
                    if cid:
                        self.save_decoded_message(cid)
                        # 剪掉已消费的比特
                        self.buffer = self.buffer[consumed:]
                    else:
                        # 暂时解不出来了，跳出循环
                        break
                
                # 5. [内存优化] 防止缓冲区无限膨胀
                # 我们的帧大概 400 bits，如果缓冲区堆积了 10000 bits 还没解出来，
                # 说明前面大概率是噪音，可以丢弃一部分陈旧数据
                MAX_BUFFER_SIZE = 10000
                if len(self.buffer) > MAX_BUFFER_SIZE:
                    drop_len = len(self.buffer) - 5000 # 保留最近 5000
                    self.buffer = self.buffer[-5000:]
                    logger.warning(f"缓冲区过大，丢弃头部 {drop_len} bits 噪音")

                # 6. 更新进度
                self.update_last_id(max_id_in_batch)

            except Exception as e:
                logger.error(f"解码循环发生错误: {e}")
                time.sleep(3) # 出错歇一会

if __name__ == "__main__":
    # 确保目录存在
    if not os.path.exists("../storage"):
        os.makedirs("../storage")
        
    decoder = ORIMDecoderService()
    decoder.run()