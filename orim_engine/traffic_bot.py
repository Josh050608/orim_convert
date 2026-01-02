#!/usr/bin/env python3
"""
ORIM Traffic Generator (Python Version)
Purpose: Continuously generate Bitcoin transactions and mine blocks to keep the network alive.
Critical: Must mine after every batch to prevent mempool congestion!
"""

import subprocess
import time
import random
import sys
import signal

# Configuration
SENDER_DIR = "/tmp/bitcoin_sender"
RPC_USER = "test"
RPC_PASSWORD = "test"
MIN_BATCH = 20
MAX_BATCH = 60
SLEEP_MIN = 0.3
SLEEP_MAX = 0.8
BLOCKS_PER_MINE = 2  # Mine 2 blocks per cycle for faster confirmation

class TrafficBot:
    def __init__(self):
        self.running = True
        self.total_txs = 0
        self.total_blocks = 0
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        print(f"\n[Traffic Bot] Received signal {signum}, shutting down gracefully...")
        print(f"[Traffic Bot] Stats: {self.total_txs} txs, {self.total_blocks} blocks")
        self.running = False
        sys.exit(0)
    
    def run_cli(self, args):
        """Execute bitcoin-cli command"""
        cmd = [
            "../bitcoin/src/bitcoin-cli",
            "-regtest",
            f"-datadir={SENDER_DIR}",
            f"-rpcuser={RPC_USER}",
            f"-rpcpassword={RPC_PASSWORD}"
        ] + args
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            return None
        except Exception as e:
            return None
    
    def send_transaction_batch(self, address, count):
        """Send a batch of transactions"""
        success_count = 0
        for i in range(count):
            result = self.run_cli(["sendtoaddress", address, "0.001"])
            if result:
                success_count += 1
        return success_count
    
    def mine_blocks(self, address, count=1):
        """Mine blocks to clear mempool and broadcast INV"""
        result = self.run_cli(["generatetoaddress", str(count), address])
        return result is not None
    
    def run(self):
        """Main traffic generation loop"""
        print("[Traffic Bot] Starting up...")
        
        # Get mining address
        address = self.run_cli(["getnewaddress"])
        if not address:
            print("[Traffic Bot] ERROR: Cannot get address from bitcoind")
            sys.exit(1)
        
        print(f"[Traffic Bot] Mining address: {address}")
        print(f"[Traffic Bot] Batch size: {MIN_BATCH}-{MAX_BATCH} txs")
        print(f"[Traffic Bot] Loop interval: {SLEEP_MIN:.1f}-{SLEEP_MAX:.1f}s")
        print("[Traffic Bot] Running (Ctrl+C to stop)...\n")
        
        loop_count = 0
        
        while self.running:
            try:
                loop_count += 1
                
                # Step A: Send transaction batch
                batch_size = random.randint(MIN_BATCH, MAX_BATCH)
                sent = self.send_transaction_batch(address, batch_size)
                self.total_txs += sent
                
                # Step B: CRITICAL - Mine blocks to force broadcast
                # Without this, mempool fills up and receiver stops getting INV messages
                if self.mine_blocks(address, BLOCKS_PER_MINE):
                    self.total_blocks += BLOCKS_PER_MINE
                    print(f"[Traffic Bot] Loop #{loop_count}: Sent {sent}/{batch_size} txs, Mined {BLOCKS_PER_MINE} blocks (Total: {self.total_txs} txs, {self.total_blocks} blocks)")
                else:
                    print(f"[Traffic Bot] Loop #{loop_count}: Sent {sent}/{batch_size} txs, MINING FAILED")
                
                # Step C: Random sleep
                sleep_time = random.uniform(SLEEP_MIN, SLEEP_MAX)
                time.sleep(sleep_time)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[Traffic Bot] ERROR in loop: {e}")
                time.sleep(2)  # Backoff on error
        
        print("[Traffic Bot] Stopped.")

if __name__ == "__main__":
    bot = TrafficBot()
    bot.run()
