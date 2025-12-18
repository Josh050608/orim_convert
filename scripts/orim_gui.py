#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, scrolledtext, font, messagebox
import sqlite3
import subprocess
import threading
import time
import os

# === 配置区域 ===
BITCOIN_CLI = "../bitcoin/src/bitcoin-cli"
DB_PATH = "orim.db"
SENDER_DIR = "/tmp/bitcoin_sender"

class ORIMGui:
    def __init__(self, root):
        self.root = root
        self.root.title("ORIM 隐蔽通信系统 (演示版)")
        self.root.geometry("1100x700") # 稍微调整高度

        # === 自动寻找可用中文字体 ===
        available_families = list(font.families())
        chinese_font_candidates = [
            "WenQuanYi Micro Hei", "文泉驿微米黑",
            "Noto Sans CJK SC", "Noto Sans CJK",
            "Microsoft YaHei", "微软雅黑",
            "SimHei", "黑体",
            "PingFang SC", "Heiti TC",
            "SimSun", "宋体",
            "Arial Unicode MS"
        ]
        
        selected_font = "Helvetica"
        for f in chinese_font_candidates:
            if f in available_families:
                selected_font = f
                break
        
        # 定义字体对象
        self.default_font = font.Font(family=selected_font, size=11)
        self.mono_font = font.Font(family="Courier New", size=10)
        self.bold_font = font.Font(family=selected_font, size=12, weight="bold")
        
        # === 样式配置 ===
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('.', font=self.default_font)
        style.configure('Treeview', font=self.default_font)
        style.configure('TButton', font=self.default_font)
        style.configure('TLabel', font=self.default_font)
        style.configure('TLabelframe.Label', font=self.bold_font)
        
        # 主布局
        main_frame = ttk.Frame(root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 顶部：系统状态
        self.status_frame = ttk.LabelFrame(main_frame, text="比特币网络状态 (Regtest)", padding="10")
        self.status_frame.pack(fill=tk.X, pady=(0, 10))
        self.lbl_blocks = ttk.Label(self.status_frame, text="区块高度: 初始化中...", font=self.bold_font, foreground="blue")
        self.lbl_blocks.pack(side=tk.LEFT, padx=20)
        self.lbl_peers = ttk.Label(self.status_frame, text="连接节点数: 初始化中...", font=self.bold_font, foreground="green")
        self.lbl_peers.pack(side=tk.LEFT, padx=20)
        
        # 中部：左右分栏
        paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # === 左侧：发送方 (Sender) ===
        sender_frame = ttk.LabelFrame(paned, text=" [发送端] Alice ", padding="10")
        paned.add(sender_frame, weight=4) 
        
        ttk.Label(sender_frame, text="1. 输入隐蔽消息 (英文/数字):", font=self.bold_font).pack(anchor="w", pady=(5,0))
        self.txt_input = tk.Text(sender_frame, height=3, width=40, font=self.default_font)
        self.txt_input.pack(fill=tk.X, pady=5)
        
        btn_queue = ttk.Button(sender_frame, text=">>> 将消息加入发送队列 >>>", command=self.queue_message)
        btn_queue.pack(fill=tk.X, pady=5)
        
        ttk.Separator(sender_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=15)
        
        ttk.Label(sender_frame, text="2. 生成掩护流量 (作为载体):", font=self.bold_font).pack(anchor="w")
        ttk.Label(sender_frame, text="提示: 消息通过打乱交易哈希顺序来传输，必须发送交易才能携带信息。", 
                 font=(selected_font, 9), foreground="#555555").pack(anchor="w", pady=(0,5))
        
        self.btn_traffic = ttk.Button(sender_frame, text="启动流量生成器 (发送 20 笔交易)", command=self.start_traffic_generation)
        self.btn_traffic.pack(fill=tk.X, pady=5)
        
        self.btn_mine = ttk.Button(sender_frame, text="挖矿 (生成 1 个区块并触发 INV)", command=self.mine_block)
        self.btn_mine.pack(fill=tk.X, pady=5)

        ttk.Label(sender_frame, text="发送队列监控:", font=self.bold_font).pack(anchor="w", pady=(15,5))
        self.list_outgoing = tk.Listbox(sender_frame, height=8, font=self.default_font, bg="#f8f9fa")
        self.list_outgoing.pack(fill=tk.BOTH, expand=True)

        # === 右侧：接收方 (Receiver) ===
        receiver_frame = ttk.LabelFrame(paned, text=" [接收端] Bob ", padding="10")
        paned.add(receiver_frame, weight=5) 
        
        # [修改] 移除了原始比特流框，只保留解码消息
        ttk.Label(receiver_frame, text="解码后的隐蔽消息 (实时):", font=self.bold_font, foreground="darkred").pack(anchor="w", pady=(5,0))
        
        # [修改] 增大了高度，占据右侧主要空间
        self.txt_decoded = scrolledtext.ScrolledText(receiver_frame, height=20, width=40, state='disabled', bg="#e9ecef", font=(selected_font, 14, "bold"))
        self.txt_decoded.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 底部：日志
        log_frame = ttk.LabelFrame(main_frame, text="系统操作日志", padding="5")
        log_frame.pack(fill=tk.X, pady=(10,0))
        self.txt_log = scrolledtext.ScrolledText(log_frame, height=5, font=self.default_font, state='disabled', bg="#fff3cd")
        self.txt_log.pack(fill=tk.BOTH)

        # 启动定时任务
        self.update_status()
        self.poll_database()

    def log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.txt_log.config(state='normal')
        self.txt_log.insert(tk.END, f"[{timestamp}] {message}\n")
        self.txt_log.see(tk.END)
        self.txt_log.config(state='disabled')

    def run_cli(self, args):
        cmd = [BITCOIN_CLI, "-regtest", f"-datadir={SENDER_DIR}", "-rpcuser=test", "-rpcpassword=test"] + args
        try:
            result = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=5).decode().strip()
            return result
        except subprocess.TimeoutExpired:
             return "Error: RPC Timeout"
        except subprocess.CalledProcessError as e:
            return f"Error: {e.output.decode()}"
        except Exception as e:
            return f"Error: {str(e)}"

    def update_status(self):
        threading.Thread(target=self._update_status_thread, daemon=True).start()
        self.root.after(3000, self.update_status)

    def _update_status_thread(self):
        try:
            height = self.run_cli(["getblockcount"])
            peers = self.run_cli(["getconnectioncount"])
            self.root.after(0, lambda: self.lbl_blocks.config(text=f"区块高度: {height}"))
            self.root.after(0, lambda: self.lbl_peers.config(text=f"连接节点数: {peers}"))
        except:
            pass

    def queue_message(self):
        msg = self.txt_input.get("1.0", tk.END).strip()
        if not msg: return
        try:
            bits = ''.join(format(ord(c), '08b') for c in msg)
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('INSERT INTO outgoing_messages (message, bits) VALUES (?, ?)', (msg, bits))
            conn.commit()
            conn.close()
            self.log(f"消息已入队: '{msg}' (长度: {len(bits)} bits)")
            self.txt_input.delete("1.0", tk.END)
            self.poll_database()
        except Exception as e:
            self.log(f"入队失败: {e}")

    def start_traffic_generation(self):
        self.btn_traffic.config(state="disabled", text="正在生成流量 (请稍候)...")
        threading.Thread(target=self._traffic_thread, daemon=True).start()

    def _traffic_thread(self):
        """
        [智能流量生成器]
        逻辑修改：不再发送固定数量，而是根据数据库中的消息剩余比特数，
        自动持续发送交易，直到消息全部传输完成。
        """
        self.log("启动智能传输：正在分析消息队列...")
        
        try:
            # 1. 获取发币地址
            addr = self.run_cli(["getnewaddress"])
            if "Error" in addr: raise Exception(addr)

            # 2. 连接数据库检查任务
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # 循环检查：只要还有未完成的消息，就持续发送交易
            while True:
                # 查询第一条未完成的消息
                cursor.execute("SELECT id, message, position, length(bits) FROM outgoing_messages WHERE position < length(bits) ORDER BY id ASC LIMIT 1")
                row = cursor.fetchone()
                
                if not row:
                    # 如果没有消息了，发几笔掩护流量后停止
                    self.log("队列已空。发送 3 笔掩护交易后停止。")
                    for _ in range(3):
                        self.run_cli(["sendtoaddress", addr, "0.0001"])
                    break
                
                msg_id, msg_content, pos, total_bits = row
                remaining = total_bits - pos
                
                # 更新 UI 状态
                self.root.after(0, lambda: self.btn_traffic.config(text=f"传输中... 剩余 {remaining} bits"))
                self.log(f"正在传输 ID {msg_id} ('{msg_content}')... 进度: {pos}/{total_bits}")
                
                # === 发送一批交易 (Burst) ===
                # 经验值：5 笔交易作为一个小批次。
                # 5! = 120 种排列 = 约 6.9 bits。
                # 如果这 5 笔被打包在一个 INV 里，能传将近 1 个字母。
                burst_size = 5
                for i in range(burst_size):
                    self.run_cli(["sendtoaddress", addr, "0.0001"])
                
                # === 关键：等待传播与反馈 ===
                # 必须等待几秒，让：
                # 1. bitcoind 生成 INV 消息
                # 2. C++ 截获并请求 Python
                # 3. Python 算出顺序并更新数据库的 position 字段
                time.sleep(2.5) 
                
                # 提交事务以获取最新数据（重新查询前不需要 commit，但为了稳健）
                conn.commit()

            conn.close()
            self.log("所有消息传输完毕！")
            
        except Exception as e:
            self.log(f"流量生成失败: {e}")
        finally:
            # 恢复按钮状态
            self.root.after(0, lambda: self.btn_traffic.config(state="normal", text="启动流量生成器 (智能模式)"))

    def mine_block(self):
        self.btn_mine.config(state="disabled", text="正在挖矿...")
        threading.Thread(target=self._mine_thread, daemon=True).start()

    def _mine_thread(self):
        self.log("正在挖矿...")
        try:
            addr = self.run_cli(["getnewaddress"])
            self.run_cli(["generatetoaddress", "1", addr])
            self.log("新区块已生成！")
        except Exception as e:
            self.log(f"挖矿失败: {e}")
        finally:
             self.root.after(0, lambda: self.btn_mine.config(state="normal", text="挖矿 (生成 1 个区块)"))

    def poll_database(self):
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # 1. 更新发送队列
            cursor.execute("SELECT id, message, position, length(bits) FROM outgoing_messages ORDER BY id DESC LIMIT 20")
            rows = cursor.fetchall()
            self.list_outgoing.delete(0, tk.END)
            for r in rows:
                progress = int((r[2] / r[3]) * 100) if r[3] > 0 else 0
                status_text = "✅ 已完成" if r[2] >= r[3] else f"⏳ 传输中 ({progress}%)"
                display_text = f"ID {r[0]} | {r[1]} | {status_text}"
                self.list_outgoing.insert(tk.END, display_text)
            
            # [修改] 已移除比特流更新逻辑

            # 2. 更新解码消息
            cursor.execute("SELECT message, decoded_at FROM decoded_messages ORDER BY id ASC")
            msgs = cursor.fetchall()
            display_msg = ""
            for m in msgs:
                time_str = m[1].split(' ')[1] if ' ' in m[1] else m[1]
                display_msg += f"[{time_str}] {m[0]}\n"
            
            self.txt_decoded.config(state='normal')
            self.txt_decoded.delete("1.0", tk.END)
            self.txt_decoded.insert(tk.END, display_msg)
            self.txt_decoded.see(tk.END)
            self.txt_decoded.config(state='disabled')

            conn.close()
        except Exception as e:
            print(f"DB Polling error: {e}")
        
        self.root.after(500, self.poll_database)

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print("警告: 数据库未找到，请先运行启动脚本！(./start_demo.sh)")
        exit(1)
    
    root = tk.Tk()
    try:
        root.tk.call('tk', 'scaling', 1.5) 
    except:
        pass
        
    app = ORIMGui(root)
    root.mainloop()
