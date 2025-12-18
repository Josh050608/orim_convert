#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import sqlite3
import time
import threading
import os
import sys

# 引入协议层和文件服务
try:
    from core.protocol import ORIMProtocol
    from file_sender import ORIMFileSender
    from file_receiver import ORIMFileReceiver
except ImportError:
    sys.path.append(os.getcwd())
    from core.protocol import ORIMProtocol
    from file_sender import ORIMFileSender
    from file_receiver import ORIMFileReceiver

class ORIMGUI:
    def __init__(self, root, db_path="orim.db"):
        self.root = root
        self.root.title("ORIM 端到端文件传输系统 - Alice 🔄 Bob")
        self.root.geometry("1400x700")
        self.db_path = db_path
        
        # 初始化文件服务
        self.file_sender = ORIMFileSender(db_path)
        self.file_receiver = ORIMFileReceiver(db_path)
        
        # 样式配置
        style = ttk.Style()
        style.configure("TButton", font=("Arial", 10))
        style.configure("TLabel", font=("Arial", 10))
        style.configure("Alice.TLabelframe", background="#FFE4E1")
        style.configure("Bob.TLabelframe", background="#E0F0FF")
        
        # === 顶部状态栏 ===
        self.status_frame = ttk.Frame(root)
        self.status_frame.pack(fill="x", padx=10, pady=5)
        
        self.lbl_status = ttk.Label(self.status_frame, text="正在初始化...", foreground="blue", font=("Arial", 11, "bold"))
        self.lbl_status.pack()

        # === 主容器：左右分栏 ===
        main_container = ttk.Frame(root)
        main_container.pack(fill="both", expand=True, padx=10, pady=5)
        
        # === 左侧：Alice (发送方) ===
        alice_frame = ttk.LabelFrame(main_container, text="👩 Alice - 文件发送方", padding=15)
        alice_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        # Alice: 文件选择区域
        file_select_frame = ttk.Frame(alice_frame)
        file_select_frame.pack(fill="x", pady=(0, 10))
        
        self.alice_file_label = ttk.Label(file_select_frame, text="未选择文件", foreground="gray", font=("Arial", 10))
        self.alice_file_label.pack(side="left", fill="x", expand=True)
        
        self.btn_select_file = ttk.Button(file_select_frame, text="📁 选择文件", command=self.select_file)
        self.btn_select_file.pack(side="right", padx=5)
        
        self.btn_upload = ttk.Button(file_select_frame, text="🚀 加密并上传", command=self.upload_file, state="disabled")
        self.btn_upload.pack(side="right")
        
        # Alice: 已发送文件列表
        sent_label = ttk.Label(alice_frame, text="已发送的文件:", font=("Arial", 10, "bold"))
        sent_label.pack(anchor="w", pady=(10, 5))
        
        # 创建Treeview显示已发送文件
        columns = ("filename", "cid", "size", "time")
        self.alice_tree = ttk.Treeview(alice_frame, columns=columns, show="headings", height=15)
        self.alice_tree.heading("filename", text="文件名")
        self.alice_tree.heading("cid", text="CID (点击复制)")
        self.alice_tree.heading("size", text="大小")
        self.alice_tree.heading("time", text="发送时间")
        
        self.alice_tree.column("filename", width=150)
        self.alice_tree.column("cid", width=300)
        self.alice_tree.column("size", width=80)
        self.alice_tree.column("time", width=120)
        
        self.alice_tree.pack(fill="both", expand=True)
        self.alice_tree.bind("<Double-1>", self.copy_cid)
        
        # Alice: 日志区域
        alice_log_label = ttk.Label(alice_frame, text="操作日志:", font=("Arial", 10, "bold"))
        alice_log_label.pack(anchor="w", pady=(10, 5))
        
        self.alice_log = scrolledtext.ScrolledText(alice_frame, height=6, state='disabled', font=("Consolas", 9))
        self.alice_log.pack(fill="both")
        
        # === 右侧：Bob (接收方) ===
        bob_frame = ttk.LabelFrame(main_container, text="👨 Bob - 文件接收方", padding=15)
        bob_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))
        
        # Bob: 接收到的文件列表
        recv_label = ttk.Label(bob_frame, text="接收到的文件:", font=("Arial", 10, "bold"))
        recv_label.pack(anchor="w", pady=(0, 5))
        
        # 创建Treeview显示接收的文件
        bob_columns = ("cid", "time", "action")
        self.bob_tree = ttk.Treeview(bob_frame, columns=bob_columns, show="headings", height=15)
        self.bob_tree.heading("cid", text="CID")
        self.bob_tree.heading("time", text="接收时间")
        self.bob_tree.heading("action", text="状态")
        
        self.bob_tree.column("cid", width=320)
        self.bob_tree.column("time", width=120)
        self.bob_tree.column("action", width=100)
        
        self.bob_tree.pack(fill="both", expand=True)
        
        # Bob: 下载按钮区域
        bob_btn_frame = ttk.Frame(bob_frame)
        bob_btn_frame.pack(fill="x", pady=(10, 0))
        
        self.btn_download = ttk.Button(bob_btn_frame, text="⬇️ 下载选中文件", command=self.download_file, state="disabled")
        self.btn_download.pack(side="left", padx=5)
        
        self.btn_refresh = ttk.Button(bob_btn_frame, text="🔄 刷新列表", command=self.refresh_received_files)
        self.btn_refresh.pack(side="left")
        
        # Bob: 日志区域
        bob_log_label = ttk.Label(bob_frame, text="操作日志:", font=("Arial", 10, "bold"))
        bob_log_label.pack(anchor="w", pady=(10, 5))
        
        self.bob_log = scrolledtext.ScrolledText(bob_frame, height=6, state='disabled', font=("Consolas", 9))
        self.bob_log.pack(fill="both")
        
        # === 启动后台轮询 ===
        self.running = True
        self.last_decoded_id = 0
        self.selected_file_path = None
        
        # Bob选中项变化时启用下载按钮
        self.bob_tree.bind("<<TreeviewSelect>>", self.on_bob_select)
        
        threading.Thread(target=self.poll_database, daemon=True).start()

    def log_alice(self, message):
        """向Alice日志窗口添加信息"""
        self.alice_log.config(state='normal')
        timestamp = time.strftime("%H:%M:%S")
        self.alice_log.insert(tk.END, f"[{timestamp}] {message}\n")
        self.alice_log.see(tk.END)
        self.alice_log.config(state='disabled')
    
    def log_bob(self, message):
        """向Bob日志窗口添加信息"""
        self.bob_log.config(state='normal')
        timestamp = time.strftime("%H:%M:%S")
        self.bob_log.insert(tk.END, f"[{timestamp}] {message}\n")
        self.bob_log.see(tk.END)
        self.bob_log.config(state='disabled')
    
    def select_file(self):
        """选择要发送的文件"""
        file_path = filedialog.askopenfilename(title="选择要发送的文件")
        if file_path:
            self.selected_file_path = file_path
            filename = os.path.basename(file_path)
            size = os.path.getsize(file_path)
            size_str = self.format_size(size)
            self.alice_file_label.config(text=f"{filename} ({size_str})", foreground="black")
            self.btn_upload.config(state="normal")
            self.log_alice(f"已选择文件: {filename}")
    
    def format_size(self, size_bytes):
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"
    
    def upload_file(self):
        """加密文件并上传到IPFS"""
        if not self.selected_file_path:
            return
        
        filename = os.path.basename(self.selected_file_path)
        self.log_alice(f"正在加密并上传 {filename}...")
        self.btn_upload.config(state="disabled")
        
        try:
            # 使用file_sender进行加密和上传
            cid, key_alias = self.file_sender.send_file(self.selected_file_path)
            
            # 获取文件信息
            size = os.path.getsize(self.selected_file_path)
            size_str = self.format_size(size)
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            
            # 添加到Alice的发送列表
            self.alice_tree.insert("", 0, values=(filename, cid, size_str, timestamp))
            
            self.log_alice(f"✅ 上传成功！")
            self.log_alice(f"CID: {cid}")
            self.log_alice(f"文件已进入发送队列，等待传输...")
            
            # 清空选择
            self.selected_file_path = None
            self.alice_file_label.config(text="未选择文件", foreground="gray")
            
            messagebox.showinfo("上传成功", f"文件已加密并上传到IPFS\n\nCID: {cid}\n\n文件已进入发送队列，等待通过区块链传输")
            
        except Exception as e:
            self.log_alice(f"❌ 上传失败: {e}")
            messagebox.showerror("上传失败", f"加密或上传文件时出错:\n{e}")
            self.btn_upload.config(state="normal")
    
    def copy_cid(self, event):
        """双击复制CID到剪贴板"""
        selection = self.alice_tree.selection()
        if selection:
            item = self.alice_tree.item(selection[0])
            cid = item['values'][1]
            self.root.clipboard_clear()
            self.root.clipboard_append(cid)
            self.log_alice(f"已复制CID到剪贴板: {cid[:20]}...")
    
    def on_bob_select(self, event):
        """Bob选中文件时启用下载按钮"""
        selection = self.bob_tree.selection()
        if selection:
            self.btn_download.config(state="normal")
        else:
            self.btn_download.config(state="disabled")
    
    def download_file(self):
        """下载选中的文件"""
        selection = self.bob_tree.selection()
        if not selection:
            return
        
        item = self.bob_tree.item(selection[0])
        cid = item['values'][0]
        
        self.log_bob(f"正在从IPFS下载文件: {cid[:20]}...")
        self.btn_download.config(state="disabled")
        
        try:
            # 使用file_receiver下载并解密
            output_filename = f"received_{int(time.time())}.bin"
            output_path = self.file_receiver.download_file(cid, output_filename)
            
            # 更新状态
            self.bob_tree.item(selection[0], values=(cid, item['values'][1], "✅ 已下载"))
            
            self.log_bob(f"✅ 下载成功！")
            self.log_bob(f"保存位置: {output_path}")
            
            messagebox.showinfo("下载成功", f"文件已下载并解密\n\n保存位置:\n{output_path}")
            
        except Exception as e:
            self.log_bob(f"❌ 下载失败: {e}")
            messagebox.showerror("下载失败", f"下载或解密文件时出错:\n{e}")
        finally:
            self.btn_download.config(state="normal")
    
    def refresh_received_files(self):
        """手动刷新接收列表"""
        self.log_bob("正在刷新接收列表...")
        # poll_database会自动更新，这里只是给用户反馈
        time.sleep(0.5)
        self.log_bob("列表已刷新")

    def poll_database(self):
        """后台线程：监控decoded_messages表获取接收的CID"""
        while self.running:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # 读取新解码的消息（CID）
                cursor.execute('SELECT id, message, decoded_at FROM decoded_messages WHERE id > ? ORDER BY id ASC', (self.last_decoded_id,))
                rows = cursor.fetchall()
                
                for row in rows:
                    msg_id, cid, timestamp = row
                    
                    # 检查是否是有效的CID
                    if cid and cid.startswith("Qm") and len(cid) == 46:
                        # 添加到Bob的接收列表
                        self.bob_tree.insert("", 0, values=(cid, timestamp, "⏳ 待下载"))
                        self.log_bob(f"📥 收到文件CID: {cid[:20]}...")
                        
                        # 播放通知音（可选）
                        self.root.bell()
                    
                    self.last_decoded_id = msg_id
                
                conn.close()
                self.lbl_status.config(text="✅ 系统正常运行 | 监控中...", foreground="green")
                
            except Exception as e:
                self.lbl_status.config(text=f"❌ 数据库错误: {e}", foreground="red")
            
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