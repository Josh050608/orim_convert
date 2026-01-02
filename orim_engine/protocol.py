import struct
import binascii

class ORIMProtocol:
    # 1. 常量定义
    # 使用不可打印字符作为帧头: 0x00FF (二进制: 0000000011111111)
    # CID是Base58编码(字符集: [A-Za-z0-9])，ASCII范围 48-122
    # 0x00 和 0xFF 不会出现在CID中，保证数据透明性
    MAGIC = 0x00FF          # 帧头 (Hex)
    # 预计算 Magic 的二进制字符串: "0000000011111111"
    MAGIC_BIN = format(MAGIC, '016b') 
    
    CID_LEN = 46            # IPFS CID 长度
    # 帧结构: Magic(16 bits) + CID(46 bytes * 8) + CRC(1 byte * 8)
    # 总比特数: 16 + 368 + 8 = 392 bits
    FRAME_BITS_LEN = 16 + (46 * 8) + 8 

    @staticmethod
    def pack_cid(cid_str: str) -> str:
        """
        [发送端 - 数据打包]
        将 CID 字符串打包成二进制帧
        
        Args:
            cid_str: IPFS CID字符串（必须以"Qm"开头，长度46字符）
            
        Returns:
            str: 二进制字符串表示的完整帧
            
        Raises:
            ValueError: 如果CID长度或格式不正确
        """
        if len(cid_str) != ORIMProtocol.CID_LEN:
            raise ValueError(f"CID length error: expected {ORIMProtocol.CID_LEN}, got {len(cid_str)}")
        if not cid_str.startswith("Qm"):
            raise ValueError("CID format error: must start with 'Qm'")

        payload_bytes = cid_str.encode('utf-8')
        crc = binascii.crc32(payload_bytes) & 0xFF
        frame = struct.pack(f'>H{ORIMProtocol.CID_LEN}sB', 
                          ORIMProtocol.MAGIC, payload_bytes, crc)
        return ''.join(format(byte, '08b') for byte in frame)

    @staticmethod
    def decode_stream(bitstream: str):
        """
        [接收端 - 比特级扫描]
        不依赖字节对齐，逐个比特滑动窗口寻找 Magic
        
        Args:
            bitstream: 二进制字符串（由'0'和'1'组成）
            
        Returns:
            tuple: (cid_str, consumed_bits)
                - cid_str: 解码出的CID字符串，如果未找到有效帧则返回None
                - consumed_bits: 消耗的比特数，如果未找到有效帧则返回0
        """
        n = len(bitstream)
        # 如果连最小帧长度都不够，直接放弃
        if n < ORIMProtocol.FRAME_BITS_LEN:
            return None, 0

        # === 核心修改：逐位扫描 ===
        # i 代表当前扫描到的比特索引
        # limit 是最后可能出现帧头的位置
        limit = n - ORIMProtocol.FRAME_BITS_LEN + 1
        
        for i in range(limit):
            # 1. 极其快速的字符串匹配：检查前16位是否是 Magic
            # 这里的切片操作在 Python 中经过优化，速度很快
            if bitstream[i : i+16] == ORIMProtocol.MAGIC_BIN:
                
                # === 2. 发现潜在帧头，尝试提取后续数据 ===
                # 提取 Payload 部分 (紧接着 Magic 后面的 46 字节)
                payload_start = i + 16
                payload_end = payload_start + (ORIMProtocol.CID_LEN * 8)
                payload_bits = bitstream[payload_start : payload_end]
                
                # 提取 CRC 部分 (紧接着 Payload 后面的 8 bits)
                crc_start = payload_end
                crc_end = crc_start + 8
                crc_bits = bitstream[crc_start : crc_end]
                
                try:
                    # 将二进制串转回字节
                    # 注意：int(str, 2) 可以处理任意长度的二进制串
                    payload_int = int(payload_bits, 2)
                    payload_bytes = payload_int.to_bytes(ORIMProtocol.CID_LEN, byteorder='big')
                    
                    crc_int = int(crc_bits, 2)
                    
                    # === 3. 校验 CRC ===
                    calc_crc = binascii.crc32(payload_bytes) & 0xFF
                    
                    if crc_int == calc_crc:
                        # ✅ 校验通过！
                        cid_str = payload_bytes.decode('utf-8')
                        
                        # 二次确认内容格式
                        if cid_str.startswith("Qm"):
                            # 计算消耗的比特数：
                            # 从当前 i 开始，加上整个帧长。
                            # i 之前的比特被视为"噪音"或"无效数据"一并消耗掉。
                            consumed_bits = i + ORIMProtocol.FRAME_BITS_LEN
                            return cid_str, consumed_bits
                            
                except Exception:
                    # 转换失败或解码失败，说明这只是偶然出现的 0xCAFE 序列
                    # 继续循环，i 自增 1，检查下一个位置
                    pass
        
        # 扫完了都没找到
        return None, 0
