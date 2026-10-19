"""Synthetic sender; this is not AirPods data. Stop with Ctrl+C."""
import argparse
import math
import socket
import struct
import time


def packet(yaw, pitch, roll=0):
    return struct.pack('<6d', 0, 0, 0, yaw, pitch, roll)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=4242)
    parser.add_argument('--seconds', type=float, default=0, help='0 means until Ctrl+C')
    args = parser.parse_args()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        start = time.monotonic()
        try:
            while not args.seconds or time.monotonic() - start < args.seconds:
                t = time.monotonic() - start
                # First 4 seconds neutral, then slow continuous motion.
                elapsed = max(0, t - 4)
                sock.sendto(packet(12 * math.sin(elapsed * .5),
                                   8 * math.sin(elapsed * .37)), ('127.0.0.1', args.port))
                time.sleep(.02)
        except KeyboardInterrupt:
            pass

if __name__ == '__main__':
    main()
