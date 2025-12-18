#!/usr/bin/env python3
"""
IPFS + Crypto Service for ORIM
文件加密上传和解密下载封装

功能：
1. 本地文件加密 + 上传到 IPFS
2. 从 IPFS 下载 + 解密到本地
3. 支持 AES-256 加密（使用 Fernet）
4. 密钥管理和持久化
"""

import os
import json
import requests
import hashlib
from pathlib import Path
from typing import Optional, Tuple
from cryptography.fernet import Fernet
import logging

logger = logging.getLogger(__name__)


class IPFSCryptoService:
    """IPFS 加密文件服务"""
    
    def __init__(self, ipfs_api_url: str = 'http://127.0.0.1:5001', 
                 key_storage_path: Optional[str] = None):
        """
        初始化 IPFS + Crypto 服务
        
        Args:
            ipfs_api_url: IPFS API 地址
            key_storage_path: 密钥存储路径（默认: storage/crypto_keys.json）
        """
        self.ipfs_api = ipfs_api_url
        self.api_add = f"{ipfs_api_url}/api/v0/add"
        self.api_cat = f"{ipfs_api_url}/api/v0/cat"
        
        # 密钥存储
        if key_storage_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            storage_dir = os.path.join(project_root, 'storage')
            os.makedirs(storage_dir, exist_ok=True)
            key_storage_path = os.path.join(storage_dir, 'crypto_keys.json')
        
        self.key_storage_path = key_storage_path
        self.keys = self._load_keys()
        
        logger.info(f"IPFSCryptoService initialized: IPFS={ipfs_api_url}, Keys={len(self.keys)}")
    
    def _load_keys(self) -> dict:
        """加载已保存的密钥"""
        if os.path.exists(self.key_storage_path):
            try:
                with open(self.key_storage_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load keys: {e}")
        return {}
    
    def _save_keys(self):
        """保存密钥到文件"""
        try:
            with open(self.key_storage_path, 'w') as f:
                json.dump(self.keys, f, indent=2)
            logger.debug(f"Saved {len(self.keys)} keys to {self.key_storage_path}")
        except Exception as e:
            logger.error(f"Failed to save keys: {e}")
    
    def generate_key(self) -> bytes:
        """生成新的加密密钥 (Fernet AES-256)"""
        return Fernet.generate_key()
    
    def encrypt_file(self, file_path: str, encryption_key: Optional[bytes] = None) -> Tuple[bytes, bytes]:
        """
        加密文件
        
        Args:
            file_path: 文件路径
            encryption_key: 加密密钥（如果为None则自动生成）
        
        Returns:
            (encrypted_data, key): 加密后的数据和使用的密钥
        """
        if encryption_key is None:
            encryption_key = self.generate_key()
        
        cipher = Fernet(encryption_key)
        
        with open(file_path, 'rb') as f:
            plaintext = f.read()
        
        encrypted = cipher.encrypt(plaintext)
        
        logger.info(f"Encrypted file: {file_path} ({len(plaintext)} -> {len(encrypted)} bytes)")
        return encrypted, encryption_key
    
    def decrypt_data(self, encrypted_data: bytes, encryption_key: bytes) -> bytes:
        """
        解密数据
        
        Args:
            encrypted_data: 加密的数据
            encryption_key: 解密密钥
        
        Returns:
            解密后的原始数据
        """
        cipher = Fernet(encryption_key)
        plaintext = cipher.decrypt(encrypted_data)
        
        logger.info(f"Decrypted data: {len(encrypted_data)} -> {len(plaintext)} bytes")
        return plaintext
    
    def upload_to_ipfs(self, data: bytes) -> str:
        """
        上传数据到 IPFS
        
        Args:
            data: 要上传的数据（通常是加密后的数据）
        
        Returns:
            CID (Content Identifier)
        """
        try:
            # 使用 IPFS HTTP API
            response = requests.post(
                self.api_add,
                files={'file': ('encrypted_file', data)},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                cid = result['Hash']
                logger.info(f"Uploaded to IPFS: {len(data)} bytes -> CID={cid}")
                return cid
            else:
                raise Exception(f"IPFS upload failed: {response.status_code} {response.text}")
        
        except Exception as e:
            logger.error(f"IPFS upload error: {e}")
            raise
    
    def download_from_ipfs(self, cid: str) -> bytes:
        """
        从 IPFS 下载数据
        
        Args:
            cid: Content Identifier
        
        Returns:
            下载的数据（通常是加密的）
        """
        try:
            response = requests.post(
                self.api_cat,
                params={'arg': cid},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.content
                logger.info(f"Downloaded from IPFS: CID={cid} -> {len(data)} bytes")
                return data
            else:
                raise Exception(f"IPFS download failed: {response.status_code}")
        
        except Exception as e:
            logger.error(f"IPFS download error: {e}")
            raise
    
    def encrypt_and_upload(self, file_path: str, key_alias: Optional[str] = None) -> Tuple[str, str]:
        """
        完整流程：加密文件 + 上传到 IPFS
        
        Args:
            file_path: 本地文件路径
            key_alias: 密钥别名（用于后续检索，默认使用文件名）
        
        Returns:
            (cid, key_alias): IPFS CID 和密钥别名
        """
        # 加密文件
        encrypted_data, encryption_key = self.encrypt_file(file_path)
        
        # 上传到 IPFS
        cid = self.upload_to_ipfs(encrypted_data)
        
        # 保存密钥（以 CID 为键）
        if key_alias is None:
            key_alias = os.path.basename(file_path)
        
        self.keys[cid] = {
            'key': encryption_key.decode('utf-8'),  # Fernet key is base64 encoded
            'alias': key_alias,
            'file_name': os.path.basename(file_path),
            'original_size': os.path.getsize(file_path)
        }
        self._save_keys()
        
        logger.info(f"Encrypted and uploaded: {file_path} -> CID={cid}")
        return cid, key_alias
    
    def download_and_decrypt(self, cid: str, output_path: str, 
                            encryption_key: Optional[bytes] = None) -> str:
        """
        完整流程：从 IPFS 下载 + 解密到本地
        
        Args:
            cid: IPFS CID
            output_path: 输出文件路径
            encryption_key: 解密密钥（如果为None则从存储中查找）
        
        Returns:
            输出文件路径
        """
        # 从 IPFS 下载
        encrypted_data = self.download_from_ipfs(cid)
        
        # 获取解密密钥
        if encryption_key is None:
            # 🔥 重新加载密钥（防止在同一进程中 Alice 添加了新密钥但 Bob 的实例还是旧的）
            self.keys = self._load_keys()
            
            if cid not in self.keys:
                raise ValueError(f"No encryption key found for CID: {cid}")
            encryption_key = self.keys[cid]['key'].encode('utf-8')
        
        # 解密数据
        plaintext = self.decrypt_data(encrypted_data, encryption_key)
        
        # 保存到文件
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(plaintext)
        
        logger.info(f"Downloaded and decrypted: CID={cid} -> {output_path}")
        return output_path
    
    def get_key_for_cid(self, cid: str) -> Optional[bytes]:
        """获取指定 CID 的解密密钥"""
        if cid in self.keys:
            return self.keys[cid]['key'].encode('utf-8')
        return None
    
    def list_stored_files(self) -> dict:
        """列出所有存储的文件信息"""
        return {
            cid: {
                'alias': info['alias'],
                'file_name': info['file_name'],
                'size': info['original_size']
            }
            for cid, info in self.keys.items()
        }


# ==========================================
# CLI 测试接口
# ==========================================

def main():
    """命令行测试"""
    import sys
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    
    service = IPFSCryptoService()
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Upload:   python ipfs_crypto_service.py upload <file_path>")
        print("  Download: python ipfs_crypto_service.py download <cid> <output_path>")
        print("  List:     python ipfs_crypto_service.py list")
        return
    
    command = sys.argv[1]
    
    if command == 'upload':
        if len(sys.argv) < 3:
            print("Error: Missing file path")
            return
        
        file_path = sys.argv[2]
        cid, alias = service.encrypt_and_upload(file_path)
        print(f"\n✅ Upload Success!")
        print(f"   CID: {cid}")
        print(f"   Alias: {alias}")
        print(f"\n   To download: python ipfs_crypto_service.py download {cid} <output_path>")
    
    elif command == 'download':
        if len(sys.argv) < 4:
            print("Error: Missing CID or output path")
            return
        
        cid = sys.argv[2]
        output_path = sys.argv[3]
        result_path = service.download_and_decrypt(cid, output_path)
        print(f"\n✅ Download Success!")
        print(f"   Saved to: {result_path}")
    
    elif command == 'list':
        files = service.list_stored_files()
        if not files:
            print("No files stored yet.")
        else:
            print(f"\nStored Files ({len(files)}):")
            for cid, info in files.items():
                print(f"  • {info['alias']} ({info['size']} bytes)")
                print(f"    CID: {cid}")
                print()
    
    else:
        print(f"Unknown command: {command}")


if __name__ == '__main__':
    main()
