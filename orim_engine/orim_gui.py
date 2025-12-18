#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import sqlite3
import time
import threading
import os
import sys

# 引入协议层以便在 GUI 里做简单的格式校验
try:
    from core.protocol import ORIMProtocol
except ImportError:
    sys.path.append(os.getcwd())
    from core.protocol import ORIMProtocol

class ORIMGUI:
    def __init__(self, root, db_path="orim.db"):
        self.root = root
        self.root.title("ORIM 隐蔽文件传输控制台")
        self.root.geometry("800x600")
        self.db_path = db_path
        
        # 样式配置
        style = ttk.Style()
        style.configure("TButton", font=("Arial", 10))
        style.configure("TLabel", font=("Arial", 10))
        
        # === 顶部状态栏 ===
        self.status_frame = ttk.LabelFrame(root, text="系统状态", padding=10)
        self.status_frame.pack(fill="x", padx=10, pady=5)
        
        self.lbl_status = ttk.Label(self.status_frame, text="正在连接数据库...", foreground="blue")
        self.lbl_status.pack(side="left")

        # === 中间接收区 ===
        self.recv_frame = ttk.LabelFrame(root, text="已接收的文件索引 (CIDs)", padding=10)
        self.recv_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.txt_received = scrolledtext.ScrolledText(self.recv_frame, height=15, state='disabled', font=("Consolas", 11))
        self.txt_received.pack(fill="both", expand=True)

        # === 底部发送区 ===
        self.send_frame = ttk.LabelFrame(root, text="发送文件索引", padding=10)
        self.send_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(self.send_frame, text="输入 IPFS CID (Qm...):").pack(side="left")
        
        self.entry_msg = ttk.Entry(self.send_frame, width=50)
        self.entry_msg.pack(side="left", padx=10)
        self.entry_msg.insert(0, "QmTestHash123456789012345678901234567890123456") # 默认填一个合法的
        
        self.btn_send = ttk.Button(self.send_frame, text="🚀 发送索引", command=self.send_message)
        self.btn_send.pack(side="left")
        
        self.btn_gen = ttk.Button(self.send_frame, text="🎲 生成随机CID", command=self.generate_random_cid)
        self.btn_gen.pack(side="left", padx=5)

        # === 启动后台轮询 ===
        self.running = True
        self.last_decoded_id = 0
        threading.Thread(target=self.poll_database, daemon=True).start()

    def log_gui(self, message):
        """向接收窗口添加日志"""
        self.txt_received.config(state='normal')
        self.txt_received.insert(tk.END, f"{message}\n")
        self.txt_received.see(tk.END)
        self.txt_received.config(state='disabled')
    
    def _log_debug_bits(self, cid, bits, source):
        """记录二进制数据到 sender_debug.log"""
        import logging
        from datetime import datetime
        
        # 获取 storage 目录的绝对路径
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        debug_log = os.path.join(project_root, 'storage', 'sender_debug.log')
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]
        log_line = f"{timestamp} [DEBUG] [NEW_MSG_{source}] CID={cid} TotalLen={len(bits)} Bits={bits}\n"
        
        with open(debug_log, 'a') as f:
            f.write(log_line)
            f.flush()
    
    def _log_debug_insert(self, msg_id, cid, bits_len):
        """记录数据库插入到 sender_debug.log"""
        import logging
        from datetime import datetime
        
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        debug_log = os.path.join(project_root, 'storage', 'sender_debug.log')
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]
        log_line = f"{timestamp} [DEBUG] [DB_INSERTED_GUI] MsgID={msg_id} CID={cid} StoredBits={bits_len}\n"
        
        with open(debug_log, 'a') as f:
            f.write(log_line)
            f.flush()

    def generate_random_cid(self):
        """辅助测试：生成一个合法的随机 CID"""
        import random
        # 必须是 46 字符，Qm 开头
        chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        random_suffix = "".join(random.choice(chars) for _ in range(44))
        cid = "Qm" + random_suffix
        self.entry_msg.delete(0, tk.END)
        self.entry_msg.insert(0, cid)

    def send_message(self):
        cid = self.entry_msg.get().strip()
        if not cid:
            return

        # 1. 简单校验
        if not cid.startswith("Qm") or len(cid) != 46:
            messagebox.showerror("格式错误", "必须是 46 位长的 IPFS CID (以 Qm 开头)")
            return

        # 2. 写入数据库 (调用 Protocol 打包)
        try:
            bits = ORIMProtocol.pack_cid(cid)
            
            # 🔬 DEBUG: Log the binary string before DB insertion
            self._log_debug_bits(cid, bits, "GUI_SEND")
            
            conn = sqlite3.connect(self.db_path)
            conn.execute('INSERT INTO outgoing_messages (message, bits) VALUES (?, ?)', (cid, bits))
            msg_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            conn.commit()
            conn.close()
            
            # 🔬 DEBUG: Log DB insertion
            self._log_debug_insert(msg_id, cid, len(bits))
            
            self.log_gui(f"[发送] 📤 {cid}")
            self.entry_msg.delete(0, tk.END)
            
        except Exception as e:
            messagebox.showerror("错误", f"发送失败: {e}")

    def poll_database(self):
        """后台线程：只读 decoded_messages 表"""
        while self.running:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # 读取新解码的消息
                # 注意：这里读取的是 decoded_messages 表
                # 这个表是由 decoder_service.py 填充的
                cursor.execute('SELECT id, message, decoded_at FROM decoded_messages WHERE id > ? ORDER BY id ASC', (self.last_decoded_id,))
                rows = cursor.fetchall()
                
                for row in rows:
                    msg_id, msg, timestamp = row
                    # 显示在界面上
                    self.log_gui(f"[{timestamp}] 📥 收到文件: {msg}")
                    # 可以在这里加一个 [下载] 按钮的逻辑
                    self.last_decoded_id = msg_id
                
                conn.close()
                self.lbl_status.config(text="系统正常 | 监控中...", foreground="green")
                
            except Exception as e:
                self.lbl_status.config(text=f"数据库错误: {e}", foreground="red")
            
            time.sleep(1)

    def on_closing(self):
        self.running = False
        self.root.destroy()

if __name__ == "__main__":
    import os
    
    # === 强行定位路径逻辑 ===
    base_dir = os.path.dirname(os.path.abspath(__file__))
    storage_dir = os.path.join(os.path.dirname(base_dir), 'storage')
    db_path_absolute = os.path.join(storage_dir, 'orim.db')
    
    if not os.path.exists(storage_dir):
        os.makedirs(storage_dir)

    print(f"🔧 GUI Database Path: {db_path_absolute}")

    root = tk.Tk()
    # 传入绝对路径
    app = ORIMGUI(root, db_path=db_path_absolute)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()