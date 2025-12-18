#!/usr/bin/env python3
"""
ORIM File Sender - GUI 集成
通过 IPFS + 加密 + 区块链隐蔽信道发送文件

使用流程：
1. 用户选择文件
2. 自动加密文件并上传到 IPFS
3. 获得 CID
4. 将 CID 通过 ORIM 区块链隐蔽信道发送
5. 接收方通过 CID 从 IPFS 下载并解密

这个模块封装了发送端逻辑
"""

import os
import sys
import sqlite3
import logging
from typing import Tuple, Optional
from pathlib import Path

# 引入 IPFS + Crypto 服务
from ipfs_crypto_service import IPFSCryptoService

# 引入 ORIM 协议
try:
    from core.protocol import ORIMProtocol
except ImportError:
    sys.path.append(os.getcwd())
    from core.protocol import ORIMProtocol

logger = logging.getLogger(__name__)


class ORIMFileSender:
    """ORIM 文件发送器"""
    
    def __init__(self, db_path: str, ipfs_api_url: str = 'http://127.0.0.1:5001'):
        """
        初始化文件发送器
        
        Args:
            db_path: ORIM 数据库路径
            ipfs_api_url: IPFS API 地址
        """
        self.db_path = db_path
        self.ipfs_service = IPFSCryptoService(ipfs_api_url=ipfs_api_url)
        
        logger.info(f"ORIMFileSender initialized: DB={db_path}")
    
    def send_file(self, file_path: str, key_alias: Optional[str] = None) -> Tuple[str, str]:
        """
        发送文件的完整流程
        
        步骤:
        1. 加密文件
        2. 上传到 IPFS
        3. 获取 CID
        4. 将 CID 插入到 ORIM 发送队列
        
        Args:
            file_path: 要发送的文件路径
            key_alias: 密钥别名（可选）
        
        Returns:
            (cid, message): IPFS CID 和发送状态消息
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_size = os.path.getsize(file_path)
        file_name = os.path.basename(file_path)
        
        logger.info(f"Sending file: {file_name} ({file_size} bytes)")
        
        try:
            # Step 1: 加密并上传到 IPFS
            cid, alias = self.ipfs_service.encrypt_and_upload(file_path, key_alias)
            logger.info(f"Encrypted and uploaded: CID={cid}")
            
            # Step 2: 将 CID 打包成 ORIM 协议格式
            # pack_cid() 已经返回 bits 字符串，不需要再转换
            bits = ORIMProtocol.pack_cid(cid)
            logger.info(f"Packed CID: {len(bits)} bits")
            
            # Step 3: 将打包后的数据插入到 ORIM 发送队列
            self._insert_to_outgoing_queue(cid, bits)
            
            message = f"✅ 文件已加密并上传到 IPFS\n"
            message += f"   文件: {file_name}\n"
            message += f"   大小: {file_size} bytes\n"
            message += f"   CID: {cid}\n"
            message += f"   状态: 已进入发送队列 ({len(bits)} bits)"
            
            logger.info(f"File queued for transmission: {cid}")
            return cid, message
        
        except Exception as e:
            logger.error(f"Failed to send file: {e}")
            raise
    
    def _insert_to_outgoing_queue(self, cid: str, bits: str):
        """将 CID bits 插入到 ORIM 发送队列"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 插入到 outgoing_messages 表
        cursor.execute('''
            INSERT INTO outgoing_messages (message, bits, position, completed_at)
            VALUES (?, ?, 0, NULL)
        ''', (cid, bits))
        
        conn.commit()
        conn.close()
        
        logger.debug(f"Inserted to outgoing queue: CID={cid}, bits={len(bits)}")
    
    def get_send_status(self) -> dict:
        """获取发送队列状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 查询发送队列
        cursor.execute('''
            SELECT id, message, position, length(bits) as total_bits, completed_at
            FROM outgoing_messages
            ORDER BY id DESC
            LIMIT 10
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        status = {
            'pending': [],
            'completed': []
        }
        
        for row in rows:
            msg_id, cid, pos, total_bits, completed_at = row
            progress = (pos / total_bits * 100) if total_bits > 0 else 0
            
            item = {
                'id': msg_id,
                'cid': cid,
                'progress': f"{progress:.1f}%",
                'transmitted': f"{pos}/{total_bits} bits"
            }
            
            if completed_at:
                status['completed'].append(item)
            else:
                status['pending'].append(item)
        
        return status


# ==========================================
# CLI 测试接口
# ==========================================

def main():
    """命令行测试"""
    import sys
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    
    if len(sys.argv) < 2:
        print("Usage: python file_sender.py <file_path>")
        return
    
    file_path = sys.argv[1]
    
    # 使用默认数据库路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    db_path = os.path.join(project_root, 'storage', 'orim.db')
    
    sender = ORIMFileSender(db_path)
    
    try:
        cid, message = sender.send_file(file_path)
        print(f"\n{message}")
        print(f"\n💡 接收方需要这个 CID 来下载文件: {cid}")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == '__main__':
    main()