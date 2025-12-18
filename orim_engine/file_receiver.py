#!/usr/bin/env python3
"""
ORIM File Receiver - 接收端逻辑
从区块链隐蔽信道接收 CID，然后从 IPFS 下载并解密文件

使用流程：
1. 监听 ORIM 解码结果（decoded_messages 表）
2. 提取 CID
3. 从 IPFS 下载加密文件
4. 使用密钥解密文件
5. 保存到本地
"""

import os
import sys
import sqlite3
import time
import logging
from typing import List, Optional
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


class ORIMFileReceiver:
    """ORIM 文件接收器"""
    
    def __init__(self, db_path: str, 
                 download_dir: Optional[str] = None,
                 ipfs_api_url: str = 'http://127.0.0.1:5001'):
        """
        初始化文件接收器
        
        Args:
            db_path: ORIM 数据库路径
            download_dir: 下载目录（默认: storage/downloads）
            ipfs_api_url: IPFS API 地址
        """
        self.db_path = db_path
        self.ipfs_service = IPFSCryptoService(ipfs_api_url=ipfs_api_url)
        
        # 设置下载目录
        if download_dir is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            download_dir = os.path.join(project_root, 'storage', 'downloads')
        
        os.makedirs(download_dir, exist_ok=True)
        self.download_dir = download_dir
        
        logger.info(f"ORIMFileReceiver initialized: DB={db_path}, Downloads={download_dir}")
    
    def get_received_cids(self, mark_as_processed: bool = True) -> List[str]:
        """
        从数据库获取接收到的 CID
        
        Args:
            mark_as_processed: 是否标记为已处理
        
        Returns:
            CID 列表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 查询 decoded_messages 表中的 CID
        # 注意：这里假设 message 字段存储的是 CID
        cursor.execute('SELECT id, message FROM decoded_messages WHERE message LIKE "Qm%"')
        rows = cursor.fetchall()
        
        cids = []
        processed_ids = []
        
        for row_id, cid in rows:
            if cid and cid.startswith('Qm'):  # IPFS CID 格式验证
                cids.append(cid)
                processed_ids.append(row_id)
        
        # 可选：标记为已处理（删除或添加标志）
        if mark_as_processed and processed_ids:
            for row_id in processed_ids:
                cursor.execute('DELETE FROM decoded_messages WHERE id = ?', (row_id,))
            conn.commit()
        
        conn.close()
        
        logger.info(f"Found {len(cids)} CIDs in decoded_messages")
        return cids
    
    def download_file(self, cid: str, output_filename: Optional[str] = None) -> str:
        """
        从 IPFS 下载并解密文件
        
        Args:
            cid: IPFS CID
            output_filename: 输出文件名（可选，默认使用 CID）
        
        Returns:
            下载后的文件路径
        """
        if output_filename is None:
            # 尝试从密钥存储获取原始文件名
            key_info = self.ipfs_service.keys.get(cid, {})
            output_filename = key_info.get('file_name', f"{cid[:16]}.bin")
        
        output_path = os.path.join(self.download_dir, output_filename)
        
        logger.info(f"Downloading file: CID={cid}")
        
        try:
            # 从 IPFS 下载并解密
            result_path = self.ipfs_service.download_and_decrypt(cid, output_path)
            logger.info(f"Downloaded and decrypted: {result_path}")
            return result_path
        
        except ValueError as e:
            if "No encryption key" in str(e):
                # 没有密钥，需要发送方提供
                logger.error(f"Missing encryption key for CID: {cid}")
                logger.info("发送方需要安全地共享密钥（例如通过另一个信道）")
                raise
            else:
                raise
        
        except Exception as e:
            logger.error(f"Failed to download file: {e}")
            raise
    
    def process_all_received(self) -> List[str]:
        """
        处理所有接收到的文件
        
        Returns:
            下载成功的文件路径列表
        """
        cids = self.get_received_cids(mark_as_processed=True)
        
        if not cids:
            logger.info("No new files to process")
            return []
        
        downloaded_files = []
        
        for cid in cids:
            try:
                file_path = self.download_file(cid)
                downloaded_files.append(file_path)
                logger.info(f"✅ Successfully downloaded: {file_path}")
            
            except Exception as e:
                logger.error(f"❌ Failed to download CID={cid}: {e}")
        
        return downloaded_files
    
    def monitor_and_download(self, interval: int = 5):
        """
        监控模式：持续监听新的 CID 并自动下载
        
        Args:
            interval: 检查间隔（秒）
        """
        logger.info(f"Starting monitor mode (interval={interval}s)")
        print(f"🔍 监听中... 按 Ctrl+C 停止")
        
        try:
            while True:
                files = self.process_all_received()
                
                if files:
                    print(f"\n📥 下载了 {len(files)} 个文件:")
                    for f in files:
                        print(f"   • {f}")
                
                time.sleep(interval)
        
        except KeyboardInterrupt:
            logger.info("Monitor stopped by user")
            print("\n👋 监听已停止")


# ==========================================
# CLI 测试接口
# ==========================================

def main():
    """命令行测试"""
    import sys
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    
    # 使用默认数据库路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    db_path = os.path.join(project_root, 'storage', 'orim.db')
    
    receiver = ORIMFileReceiver(db_path)
    
    if len(sys.argv) > 1 and sys.argv[1] == 'monitor':
        # 监控模式
        receiver.monitor_and_download()
    
    elif len(sys.argv) > 1 and sys.argv[1] == 'download':
        # 手动下载指定 CID
        if len(sys.argv) < 3:
            print("Usage: python file_receiver.py download <cid>")
            return
        
        cid = sys.argv[2]
        try:
            file_path = receiver.download_file(cid)
            print(f"\n✅ Downloaded: {file_path}")
        except Exception as e:
            print(f"\n❌ Error: {e}")
    
    else:
        # 处理所有接收到的文件
        print("📥 检查接收队列...")
        files = receiver.process_all_received()
        
        if files:
            print(f"\n✅ 下载了 {len(files)} 个文件:")
            for f in files:
                print(f"   • {f}")
        else:
            print("\n没有新文件")
        
        print("\n💡 使用方法:")
        print("  监控模式: python file_receiver.py monitor")
        print("  手动下载: python file_receiver.py download <cid>")


if __name__ == '__main__':
    main()
