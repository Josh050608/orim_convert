#!/usr/bin/env python3
"""
ORIM Covert Channel Server
Based on "Blockchain-Based Covert Communication: A Detection Attack and Efficient Improvement"

This server receives inventory (inv) messages from Bitcoin Core via ZMQ,
applies the ORIM permutation-based steganography scheme, and returns
reordered transaction/block hashes.

Architecture:
- Sender Side: Reorders hashes based on secret message bits using PRF + Complete Binary Tree mapping
- Receiver Side: Extracts secret message bits by computing permutation rank
"""

import zmq
import json
import hashlib
import hmac
import sqlite3
import sys
import logging
from typing import List, Tuple, Dict
from datetime import datetime
from math import factorial, log2

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('orim_server.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class ORIMServer:
    """ORIM Covert Channel Server implementing the complete ORIM scheme"""
    
    def __init__(self, zmq_endpoint: str, prf_key: bytes, db_path: str):
        """
        Initialize ORIM server
        
        Args:
            zmq_endpoint: ZMQ endpoint to bind (e.g., "tcp://*:5555")
            prf_key: PRF key for obfuscating hash values (32 bytes recommended)
            db_path: Path to SQLite database for storing secret messages
        """
        self.zmq_endpoint = zmq_endpoint
        self.prf_key = prf_key
        self.db_path = db_path
        
        # Initialize ZMQ
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.bind(zmq_endpoint)
        logger.info(f"ORIM Server listening on {zmq_endpoint}")
        
        # Initialize database
        self._init_database()
        
        # Statistics
        self.stats = {
            'sent_messages': 0,
            'received_messages': 0,
            'total_bits_sent': 0,
            'total_bits_received': 0,
            'errors': 0
        }
    
    def _init_database(self):
        """Initialize SQLite database for storing secret messages"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table for outgoing secret messages (sender queue)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS outgoing_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT NOT NULL,
                bits TEXT NOT NULL,
                position INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP NULL
            )
        ''')
        
        # Table for incoming secret messages (receiver buffer)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS incoming_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                peer_id INTEGER NOT NULL,
                bits TEXT NOT NULL,
                received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Table for reconstructed messages
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS decoded_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT NOT NULL,
                decoded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {self.db_path}")
    
    def prf(self, hash_hex: str) -> int:
        """
        Pseudo-Random Function (PRF) to compute obfuscated value
        
        Args:
            hash_hex: Transaction/block hash as hex string
            
        Returns:
            Integer obfuscated value derived from HMAC-SHA256
        """
        # Use HMAC-SHA256 as PRF
        hash_bytes = bytes.fromhex(hash_hex)
        hmac_obj = hmac.new(self.prf_key, hash_bytes, hashlib.sha256)
        prf_output = hmac_obj.digest()
        
        # Convert first 8 bytes to integer
        return int.from_bytes(prf_output[:8], byteorder='big')
    
    def compute_obfuscated_values(self, hashes: List[str]) -> List[int]:
        """
        Compute obfuscated values for a list of hashes
        
        Args:
            hashes: List of transaction/block hashes
            
        Returns:
            List of obfuscated integer values
        """
        return [self.prf(h) for h in hashes]
    
    def factorial_number_system(self, rank: int, n: int) -> List[int]:
        """
        Convert rank to permutation using Factorial Number System (Lehmer code)
        
        Args:
            rank: Integer rank (0 to n!-1)
            n: Size of permutation
            
        Returns:
            Lehmer code representation [c_{n-1}, c_{n-2}, ..., c_1, c_0]
        """
        lehmer = []
        for i in range(n, 0, -1):
            fact = factorial(i - 1)
            c = rank // fact
            lehmer.append(c)
            rank %= fact
        return lehmer
    
    def lehmer_to_permutation(self, lehmer: List[int]) -> List[int]:
        """
        Convert Lehmer code to permutation
        
        Args:
            lehmer: Lehmer code [c_{n-1}, ..., c_0]
            
        Returns:
            Permutation as list of indices
        """
        n = len(lehmer)
        available = list(range(n))
        permutation = []
        
        for c in lehmer:
            permutation.append(available.pop(c))
        
        return permutation
    
    def permutation_to_lehmer(self, permutation: List[int]) -> List[int]:
        """
        Convert permutation to Lehmer code
        
        Args:
            permutation: Permutation as list of indices
            
        Returns:
            Lehmer code representation
        """
        n = len(permutation)
        lehmer = []
        
        for i in range(n):
            count = 0
            for j in range(i + 1, n):
                if permutation[j] < permutation[i]:
                    count += 1
            lehmer.append(count)
        
        return lehmer
    
    def lehmer_to_rank(self, lehmer: List[int]) -> int:
        """
        Convert Lehmer code to rank
        
        Args:
            lehmer: Lehmer code [c_{n-1}, ..., c_0]
            
        Returns:
            Integer rank
        """
        rank = 0
        n = len(lehmer)
        
        for i, c in enumerate(lehmer):
            rank += c * factorial(n - 1 - i)
        
        return rank
    
    def bits_to_rank(self, bits: str, n: int) -> Tuple[int, int]:
        """
        Convert secret bits to permutation rank using Complete Binary Tree mapping
        (ORIM Algorithm 2: Data Encoding)
        
        The Complete Binary Tree approach handles the fact that n! is rarely a power of 2:
        - If 2^(m-1) < n! ≤ 2^m
        - First (2^m - n!) permutations encode m bits
        - Remaining (2*n! - 2^m) permutations encode m-1 bits
        
        Args:
            bits: Secret bit string (e.g., "101101")
            n: Number of elements to permute
            
        Returns:
            Tuple of (rank, bits_consumed)
            - rank: Permutation rank (0 to n!-1)
            - bits_consumed: Number of bits actually encoded (m or m-1)
        """
        n_factorial = factorial(n)
        
        # Calculate m such that 2^(m-1) < n! ≤ 2^m
        m = 1
        while (1 << m) < n_factorial:  # 2^m < n!
            m += 1
        
        # Now 2^(m-1) < n! ≤ 2^m
        threshold = (1 << m) - n_factorial  # 2^m - n!
        
        # Algorithm 2: Data Encoding
        # Special case: if n! is a perfect power of 2 (threshold = 0),
        # all ranks encode exactly m bits
        if threshold == 0:
            # Perfect power of 2: all ranks use m bits
            if len(bits) >= m:
                data_m = int(bits[:m], 2)
            else:
                data_m = int(bits.ljust(m, '0'), 2)
            rank = data_m
            bits_consumed = min(len(bits), m)
        elif len(bits) >= m:
            # Try to use m bits
            data_m = int(bits[:m], 2)
            
            if data_m < threshold:
                # Case 1: First 2^m - n! permutations encode m bits
                # Rank = data_m (which is < threshold)
                rank = data_m
                bits_consumed = m
            else:
                # Case 2: Remaining permutations encode m-1 bits
                # Use m-1 bits to select from second part of tree
                data_m_minus_1 = int(bits[:m-1], 2)
                # Rank = threshold + data_{m-1}
                rank = threshold + data_m_minus_1
                bits_consumed = m - 1
        elif len(bits) >= m - 1:
            # Only have m-1 bits available, use second part of tree
            data_m_minus_1 = int(bits[:m-1], 2)
            rank = threshold + data_m_minus_1
            bits_consumed = m - 1
        else:
            # Not enough bits, pad with zeros
            data = int(bits.ljust(m-1, '0'), 2)
            rank = threshold + data
            bits_consumed = len(bits)
        
        # Ensure rank is within valid range
        rank = min(rank, n_factorial - 1)
        
        return rank, bits_consumed
    
    def rank_to_bits(self, rank: int, n: int) -> str:
        """
        Convert permutation rank back to secret bits using Complete Binary Tree
        (ORIM Algorithm 4: Data Decoding)
        
        Variable-length decoding based on which part of the tree the rank falls into.
        
        Args:
            rank: Permutation rank (0 to n!-1)
            n: Number of elements in permutation
            
        Returns:
            Binary string representing secret bits (length m or m-1)
        """
        n_factorial = factorial(n)
        
        # Calculate m such that 2^(m-1) < n! ≤ 2^m
        m = 1
        while (1 << m) < n_factorial:
            m += 1
        
        threshold = (1 << m) - n_factorial  # 2^m - n!
        
        # Algorithm 4: Data Decoding
        # Special case: if n! is a perfect power of 2 (threshold = 0),
        # all ranks encode exactly m bits
        if threshold == 0:
            # Perfect power of 2: all ranks use m bits
            bits = bin(rank)[2:].zfill(m)
        elif rank < threshold:
            # Case 1: Rank in first part of tree → m bits
            # data = rank
            bits = bin(rank)[2:].zfill(m)
        else:
            # Case 2: Rank in second part of tree → m-1 bits
            # data = rank - threshold
            data = rank - threshold
            bits = bin(data)[2:].zfill(m - 1)
        
        return bits
    
    def get_next_secret_bits(self, n: int) -> Tuple[str, int]:
        """
        Get next chunk of secret bits from database (sender side)
        Uses variable-length encoding, so we fetch max possible bits
        
        Args:
            n: Number of hashes (determines bit capacity)
            
        Returns:
            Tuple of (bits_string, message_id)
        """
        # Calculate max capacity (m bits where 2^(m-1) < n! ≤ 2^m)
        n_factorial = factorial(n)
        m = 1
        while (1 << m) < n_factorial:
            m += 1
        max_capacity = m  # Maximum bits we might need
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get the first incomplete message
        cursor.execute('''
            SELECT id, bits, position
            FROM outgoing_messages
            WHERE completed_at IS NULL
            ORDER BY id
            LIMIT 1
        ''')
        
        row = cursor.fetchone()
        
        if not row:
            # No messages to send
            conn.close()
            return ("0" * max_capacity, -1)  # Send dummy bits
        
        msg_id, full_bits, position = row
        
        # Extract next chunk (fetch max_capacity bits)
        chunk = full_bits[position:position + max_capacity]
        
        # Pad if necessary
        if len(chunk) < max_capacity:
            chunk = chunk.ljust(max_capacity, '0')
        
        # Note: We don't update position yet - will do after encoding
        # to know actual bits consumed
        
        conn.commit()
        conn.close()
        
        return (chunk, msg_id)
    
    def store_received_bits(self, peer_id: int, bits: str):
        """
        Store received secret bits (receiver side)
        
        Args:
            peer_id: Peer node ID
            bits: Extracted secret bits
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO incoming_messages (peer_id, bits)
            VALUES (?, ?)
        ''', (peer_id, bits))
        
        conn.commit()
        conn.close()
        
        # Try to reconstruct messages
        self._try_decode_messages()
    
    def _try_decode_messages(self):
        """Attempt to decode received bits into messages"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all undecoded bits in order
        cursor.execute('''
            SELECT bits FROM incoming_messages
            ORDER BY received_at
        ''')
        
        all_bits = ''.join(row[0] for row in cursor.fetchall())
        
        # Try to decode as ASCII (8 bits per character)
        if len(all_bits) >= 8:
            byte_count = len(all_bits) // 8
            message_bytes = []
            
            for i in range(byte_count):
                byte_bits = all_bits[i*8:(i+1)*8]
                try:
                    byte_val = int(byte_bits, 2)
                    if 32 <= byte_val <= 126:  # Printable ASCII
                        message_bytes.append(chr(byte_val))
                    else:
                        break
                except:
                    break
            
            if message_bytes:
                decoded_message = ''.join(message_bytes)
                cursor.execute('''
                    INSERT INTO decoded_messages (message)
                    VALUES (?)
                ''', (decoded_message,))
                conn.commit()
                logger.info(f"Decoded message: {decoded_message}")
        
        conn.close()
    
    def handle_send_request(self, request: Dict) -> Dict:
        """
        Handle sender request: reorder hashes based on secret message
        (ORIM Algorithm 2: Data Encoding - Sender Side)
        
        Args:
            request: JSON request from C++
            
        Returns:
            JSON response with reordered hashes
        """
        try:
            peer_id = request['peer_id']
            inv_type = request['inv_type']
            hashes = request['hashes']
            n = len(hashes)
            
            if n < 2:
                # Cannot encode data with <2 hashes
                return {
                    'status': 'success',
                    'reordered_hashes': hashes
                }
            
            # Step 1: Compute obfuscated values V = PRF(H)
            obfuscated_values = self.compute_obfuscated_values(hashes)
            
            # Step 2: Get natural sort order of obfuscated values
            # This establishes the "canonical" order for the permutation
            indexed_values = [(v, i) for i, v in enumerate(obfuscated_values)]
            indexed_values.sort()  # Sort by obfuscated value ascending
            natural_order = [i for v, i in indexed_values]
            
            # Step 3: Get next secret bits from database
            secret_bits, msg_id = self.get_next_secret_bits(n)
            
            # Step 4: Convert bits to target permutation using Algorithm 2
            # This uses Complete Binary Tree mapping (variable-length)
            target_rank, bits_consumed = self.bits_to_rank(secret_bits, n)
            
            # Update database with actual bits consumed
            if msg_id != -1:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT bits, position FROM outgoing_messages WHERE id = ?
                ''', (msg_id,))
                row = cursor.fetchone()
                
                if row:
                    full_bits, position = row
                    new_position = position + bits_consumed
                    
                    if new_position >= len(full_bits):
                        # Message complete
                        cursor.execute('''
                            UPDATE outgoing_messages
                            SET position = ?, completed_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        ''', (new_position, msg_id))
                        logger.info(f"Completed sending message ID {msg_id}")
                    else:
                        cursor.execute('''
                            UPDATE outgoing_messages
                            SET position = ?
                            WHERE id = ?
                        ''', (new_position, msg_id))
                
                conn.commit()
                conn.close()
            
            # Step 5: Convert rank to actual permutation using Lehmer code
            lehmer = self.factorial_number_system(target_rank, n)
            target_permutation = self.lehmer_to_permutation(lehmer)
            
            # Step 6: Apply target permutation to natural order
            # reordered[i] = natural_order[target_permutation[i]]
            final_indices = [natural_order[target_permutation[i]] for i in range(n)]
            
            # Step 7: Reorder original hashes
            reordered_hashes = [hashes[idx] for idx in final_indices]
            
            # Update statistics
            self.stats['sent_messages'] += 1
            self.stats['total_bits_sent'] += bits_consumed
            
            logger.info(f"Sender: Encoded {bits_consumed} bits into {n} {inv_type} hashes for peer {peer_id} (rank={target_rank})")
            
            return {
                'status': 'success',
                'reordered_hashes': reordered_hashes,
                'debug': {
                    'bits_encoded': bits_consumed,
                    'message_id': msg_id,
                    'rank': target_rank
                }
            }
            
        except Exception as e:
            logger.error(f"Error in handle_send_request: {e}", exc_info=True)
            self.stats['errors'] += 1
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def handle_receive_request(self, request: Dict) -> Dict:
        """
        Handle receiver request: extract secret bits from received hashes
        (ORIM Algorithm 4: Data Decoding - Receiver Side)
        
        Critical: Must sort obfuscated values to establish canonical order,
        then determine what permutation was applied.
        
        Args:
            request: JSON request from C++
            
        Returns:
            JSON acknowledgment
        """
        try:
            peer_id = request['peer_id']
            inv_type = request['inv_type']
            hashes = request['hashes']
            n = len(hashes)
            
            if n < 2:
                return {'status': 'success', 'message': 'Too few hashes'}
            
            # Step 1: Compute obfuscated values V' = PRF(H')
            # These are the PRF values in the RECEIVED order
            obfuscated_values = self.compute_obfuscated_values(hashes)
            
            # Step 2: Sort obfuscated values to get canonical order
            # This is CRITICAL - we need to know what the "natural" sorted order is
            indexed_values = [(v, i) for i, v in enumerate(obfuscated_values)]
            sorted_indexed = sorted(indexed_values)  # Sort by obfuscated value
            
            # Step 3: Determine the permutation
            # The received order is a permutation of the sorted order
            # We need to find which permutation was applied
            
            # sorted_order[i] = original index of i-th smallest obfuscated value
            sorted_order = [original_idx for v, original_idx in sorted_indexed]
            
            # Now we need the inverse: given the received order (0,1,2,...,n-1),
            # what positions do they have in the sorted order?
            # Create inverse mapping: position in sorted order → position in received order
            sorted_to_received = {sorted_idx: pos for pos, sorted_idx in enumerate(sorted_order)}
            
            # The permutation is: for each position in sorted order,
            # where does it appear in received order?
            # received_permutation[i] = where does sorted_order[i] appear in received order
            received_permutation = [sorted_to_received[i] for i in range(n)]
            
            # Step 4: Convert permutation to rank using Lehmer code
            lehmer = self.permutation_to_lehmer(received_permutation)
            rank = self.lehmer_to_rank(lehmer)
            
            # Step 5: Convert rank to secret bits using Algorithm 4 (variable-length)
            secret_bits = self.rank_to_bits(rank, n)
            
            # Step 6: Store received bits
            self.store_received_bits(peer_id, secret_bits)
            
            # Update statistics
            self.stats['received_messages'] += 1
            self.stats['total_bits_received'] += len(secret_bits)
            
            logger.info(f"Receiver: Extracted {len(secret_bits)} bits from {n} {inv_type} hashes from peer {peer_id} (rank={rank})")
            
            return {
                'status': 'success',
                'extracted_bits': secret_bits,
                'debug': {
                    'bits_extracted': len(secret_bits),
                    'rank': rank
                }
            }
            
        except Exception as e:
            logger.error(f"Error in handle_receive_request: {e}", exc_info=True)
            self.stats['errors'] += 1
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def run(self):
        """Main server loop"""
        logger.info("ORIM Server started. Waiting for requests...")
        
        try:
            while True:
                # Receive request
                message = self.socket.recv_string()
                request = json.loads(message)
                
                # Route request
                if request['direction'] == 'send':
                    response = self.handle_send_request(request)
                elif request['direction'] == 'receive':
                    response = self.handle_receive_request(request)
                else:
                    response = {
                        'status': 'error',
                        'message': f"Unknown direction: {request['direction']}"
                    }
                
                # Send response
                self.socket.send_string(json.dumps(response))
                
        except KeyboardInterrupt:
            logger.info("Server interrupted by user")
        except Exception as e:
            logger.error(f"Fatal error in server loop: {e}", exc_info=True)
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Clean shutdown"""
        logger.info("Shutting down ORIM server...")
        logger.info(f"Statistics: {self.stats}")
        self.socket.close()
        self.context.term()
        logger.info("Server shutdown complete")


def add_secret_message(db_path: str, message: str):
    """
    Add a secret message to the outgoing queue
    
    Args:
        db_path: Path to database
        message: Secret message to send
    """
    # Convert message to binary
    bits = ''.join(format(ord(c), '08b') for c in message)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO outgoing_messages (message, bits)
        VALUES (?, ?)
    ''', (message, bits))
    
    conn.commit()
    conn.close()
    
    print(f"Added message: '{message}' ({len(bits)} bits)")


def run_unit_tests():
    """
    Unit tests to verify Algorithm 2 and Algorithm 4 correctness
    Tests the Complete Binary Tree variable-length encoding
    """
    print("=" * 70)
    print("ORIM ALGORITHM VERIFICATION TESTS")
    print("=" * 70)
    print()
    
    # Create test server
    server = ORIMServer('tcp://*:9999', b'test_key', ':memory:')
    
    # Test 1: Verify bits_to_rank and rank_to_bits are inverses
    print("Test 1: Round-trip encoding/decoding")
    print("-" * 70)
    test_cases = [
        (2, "1"),                           # n=2: m=1, needs 1 bit
        (3, "10"),                          # n=3: m=3, needs 2-3 bits  
        (5, "101010"),                      # n=5: m=7, needs 6-7 bits
        (10, "1101011011010110110101"),    # n=10: m=22, needs 21-22 bits (22 bits provided)
    ]
    
    all_passed = True
    for n, original_bits in test_cases:
        rank, bits_consumed = server.bits_to_rank(original_bits, n)
        decoded_bits = server.rank_to_bits(rank, n)
        
        n_fact = factorial(n)
        m = 1
        while (1 << m) < n_fact:
            m += 1
        threshold = (1 << m) - n_fact
        
        # The decoded bits should match the consumed portion of the input
        expected = original_bits[:bits_consumed]
        passed = decoded_bits == expected
        
        all_passed = all_passed and passed
        
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} | n={n} | Input: '{original_bits}' ({len(original_bits)} bits) → Rank: {rank} → Output: '{decoded_bits}' ({len(decoded_bits)} bits)")
        print(f"       | n!={n_fact}, m={m}, threshold={threshold}, bits_consumed={bits_consumed}")
    
    print()
    
    # Test 2: Verify variable-length encoding properties
    print("Test 2: Variable-length encoding properties")
    print("-" * 70)
    
    for n in [3, 5, 10]:
        n_fact = factorial(n)
        m = 1
        while (1 << m) < n_fact:
            m += 1
        threshold = (1 << m) - n_fact
        
        print(f"n={n}: n!={n_fact}, 2^{m-1}={1<<(m-1)}, 2^{m}={1<<m}")
        print(f"  Threshold (2^m - n!): {threshold}")
        print(f"  Ranks 0..{threshold-1} encode {m} bits")
        print(f"  Ranks {threshold}..{n_fact-1} encode {m-1} bits")
        
        # Verify first part
        test_rank = 0 if threshold > 0 else threshold
        bits_0 = server.rank_to_bits(test_rank, n)
        print(f"  Rank {test_rank} → '{bits_0}' ({len(bits_0)} bits)")
        
        # Verify second part
        if threshold < n_fact - 1:
            test_rank = threshold
            bits_t = server.rank_to_bits(test_rank, n)
            print(f"  Rank {test_rank} → '{bits_t}' ({len(bits_t)} bits)")
        
        print()
    
    # Test 3: Verify permutation logic
    print("Test 3: Sender-Receiver permutation consistency")
    print("-" * 70)
    
    # Simulate sender encoding
    test_bits = "101101"
    n = 5
    # Generate proper 64-character hex hashes (like Bitcoin transaction hashes)
    test_hashes = [f"{i:064x}" for i in range(n)]
    
    # Sender: compute PRF and sort
    obf_values = [server.prf(h) for h in test_hashes]
    indexed = [(v, i) for i, v in enumerate(obf_values)]
    indexed.sort()
    natural_order = [i for v, i in indexed]
    
    # Sender: encode bits to rank to permutation
    rank, bits_consumed = server.bits_to_rank(test_bits, n)
    lehmer = server.factorial_number_system(rank, n)
    target_perm = server.lehmer_to_permutation(lehmer)
    
    # Apply permutation to get reordered indices
    final_indices = [natural_order[target_perm[i]] for i in range(n)]
    reordered_hashes = [test_hashes[idx] for idx in final_indices]
    
    print(f"Sender:")
    print(f"  Original bits: '{test_bits}'")
    print(f"  Bits consumed: {bits_consumed}")
    print(f"  Rank: {rank}")
    print(f"  Original hashes: {test_hashes}")
    print(f"  Reordered hashes: {reordered_hashes}")
    print()
    
    # Receiver: decode from reordered hashes
    recv_obf_values = [server.prf(h) for h in reordered_hashes]
    recv_indexed = [(v, i) for i, v in enumerate(recv_obf_values)]
    recv_sorted = sorted(recv_indexed)
    recv_sorted_order = [original_idx for v, original_idx in recv_sorted]
    
    sorted_to_received = {sorted_idx: pos for pos, sorted_idx in enumerate(recv_sorted_order)}
    recv_perm = [sorted_to_received[i] for i in range(n)]
    
    recv_lehmer = server.permutation_to_lehmer(recv_perm)
    recv_rank = server.lehmer_to_rank(recv_lehmer)
    recv_bits = server.rank_to_bits(recv_rank, n)
    
    print(f"Receiver:")
    print(f"  Received hashes: {reordered_hashes}")
    print(f"  Decoded rank: {recv_rank}")
    print(f"  Decoded bits: '{recv_bits}'")
    print()
    
    expected_bits = test_bits[:bits_consumed]
    match = recv_bits == expected_bits
    status = "✓ PASS" if match else "✗ FAIL"
    print(f"{status} | Sent: '{expected_bits}' | Received: '{recv_bits}' | Match: {match}")
    print()
    
    print("=" * 70)
    if all_passed and match:
        print("ALL TESTS PASSED ✓")
    else:
        print("SOME TESTS FAILED ✗")
    print("=" * 70)
    print()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='ORIM Covert Channel Server')
    parser.add_argument('--endpoint', default='tcp://*:5555',
                       help='ZMQ endpoint (default: tcp://*:5555)')
    parser.add_argument('--key', default='default_secret_key_change_me',
                       help='PRF secret key')
    parser.add_argument('--db', default='orim.db',
                       help='Database path (default: orim.db)')
    parser.add_argument('--add-message', metavar='MESSAGE',
                       help='Add a secret message to send queue')
    parser.add_argument('--test', action='store_true',
                       help='Run unit tests to verify algorithms')
    
    args = parser.parse_args()
    
    # If running tests, do that and exit
    if args.test:
        run_unit_tests()
        sys.exit(0)
    
    # If adding a message, do that and exit
    if args.add_message:
        add_secret_message(args.db, args.add_message)
        sys.exit(0)
    
    # Start server
    prf_key = args.key.encode('utf-8')
    server = ORIMServer(args.endpoint, prf_key, args.db)
    server.run()
