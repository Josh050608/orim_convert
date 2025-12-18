def decode_bits(binary_string):
    # 1. 去掉空格和换行
    binary_string = binary_string.strip().replace(" ", "")
    
    print(f"📊 总比特数: {len(binary_string)}")
    
    # 2. 尝试按 8 位一组进行分割 (标准 ASCII)
    bytes_list = []
    chars_list = []
    
    print("\n🔍 --- 逐字节解码分析 ---")
    print(f"{'INDEX':<6} {'BINARY':<10} {'HEX':<6} {'CHAR':<6}")
    print("-" * 30)
    
    for i in range(0, len(binary_string), 8):
        # 取 8 位
        byte = binary_string[i:i+8]
        
        # 如果不够 8 位（末尾），补 0
        if len(byte) < 8:
            byte = byte.ljust(8, '0')
            
        # 转换为整数
        val = int(byte, 2)
        
        # 转换为字符 (只显示可打印字符，其他的用 . 代替)
        if 32 <= val <= 126:
            char = chr(val)
        else:
            char = '.'
            
        bytes_list.append(hex(val))
        chars_list.append(char)
        
        # 打印前 20 个字节和非空字节的详细信息，防止刷屏
        if val != 0: 
            print(f"{i//8:<6} {byte:<10} {hex(val):<6} {char:<6}")

    # 3. 拼接完整字符串
    full_text = "".join(chars_list)
    
    print("-" * 30)
    print("\n📝 [完整解码结果]:")
    print(f"[{full_text}]")
    
    # 4. 智能分析
    print("\n🕵️ [侦探分析]:")
    if "Qm" in full_text:
        print("✅ 发现 IPFS CID 特征 (以 Qm 开头)")
        start = full_text.find("Qm")
        print(f"   -> 提取 CID: {full_text[start:start+46]}")
    else:
        print("⚠️ 未发现标准的 'Qm' 开头的 CID。")
        
    if binary_string.startswith("11001010"):
        print("✅ 发现 Magic Header (0xCA) - 协议头匹配")
    else:
        print("❌ 未发现 Magic Header (0xCA)")

# === 你的数据 ===
data = "110000010111111001001111111110101110000101010101100110111010001001000011000010111001101101000001100100110010001100110011010000110101001101100011011100111000001110010011000000110001001100100011001100110100001101010011011000110111001100000111001001100000011000100110010001100110011010000110101001101100011011100111000001110010011000000110001001100100011001100110100011001001111011011000000000000000000000000000000000000000000"

decode_bits(data)