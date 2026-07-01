#!/usr/bin/env python3
"""
Serial -> TCP multiplexer for a USB-connected Meshtastic node (hardened).

nRF52 boards (e.g. T1000-E) have no WiFi, so they can't expose the native TCP
API (port 4403). This bridge owns the USB serial connection and re-serves it as a
standard Meshtastic TCP endpoint on the LAN. Meshtastic serial and TCP share the
same wire framing (0x94 0xc3 <len_hi> <len_lo> <protobuf>).

Hardened over the naive relay in two ways:

  (a) Auto-reconnect: if the USB port drops or re-enumerates (moving a tracker
      around does this constantly -> "Errno 6: Device not configured"), the bridge
      closes the stale handle, drops all TCP clients (so their libraries reconnect
      and re-handshake against the fresh device), rediscovers /dev/cu.usbmodem*,
      and reopens -- without ever dropping the TCP listener.

  (b) Frame-aware multiplexing: client->device bytes are parsed into COMPLETE
      Meshtastic frames per client and written to the serial port atomically under
      a lock. This prevents two clients' partial frames from interleaving on the
      wire. device->client bytes are broadcast raw; TCP preserves per-client order
      and each client's parser reassembles frames, so that direction is fine.

      A real node's serial API only handles ONE config handshake (wantConfig ->
      config stream) at a time, so concurrent connects would starve each other.
      The bridge therefore serializes each client's opening handshake behind a
      lock held for a short window; once configured, clients' data traffic
      (heartbeats, messages) flows concurrently without the lock.

Usage:  python3 serial-tcp-bridge.py [PORT_DEV] [TCP_PORT]
        defaults: PORT_DEV=first /dev/cu.usbmodem*, TCP_PORT=4403
"""
import sys, glob, socket, threading, time
import serial as pyserial

START1, START2 = 0x94, 0xc3
MAX_FRAME = 512                      # meshtastic MAX_TO_FROM_RADIO_SIZE
DEV_GLOB = "/dev/cu.usbmodem*"
WANT_DEV = sys.argv[1] if len(sys.argv) > 1 else None
TCP_PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 4403

ser = None
ser_lock = threading.Lock()         # guards the `ser` handle + all writes to it
clients = set()
clients_lock = threading.Lock()
handshake_lock = threading.Lock()   # only one client's opening config handshake at a time
HANDSHAKE_WINDOW = 4.0              # seconds a client holds the handshake lock after its first frame

def log(*a): print("[bridge]", *a, flush=True)

def find_dev():
    if WANT_DEV:
        import os
        if os.path.exists(WANT_DEV):
            return WANT_DEV
    m = sorted(glob.glob(DEV_GLOB))
    return m[0] if m else None

def open_serial():
    """(Re)open the serial port, rediscovering the device path. Blocks until open."""
    global ser
    while True:
        dev = find_dev()
        if dev:
            try:
                s = pyserial.Serial(dev, 115200, exclusive=True, timeout=0.3, write_timeout=2)
                with ser_lock:
                    ser = s
                log(f"opened serial {dev}")
                return
            except Exception as e:
                log(f"open {dev} failed: {e}; retrying")
        else:
            log("no /dev/cu.usbmodem* present; waiting for node")
        time.sleep(1.5)

def drop_all_clients():
    with clients_lock:
        for c in list(clients):
            try: c.close()
            except Exception: pass
        clients.clear()

def broadcast(data):
    with clients_lock:
        dead = []
        for c in clients:
            try: c.sendall(data)
            except Exception: dead.append(c)
        for c in dead:
            clients.discard(c)
            try: c.close()
            except Exception: pass

def serial_reader():
    """Read device->host bytes and broadcast raw to all clients; reconnect on error."""
    global ser
    while True:
        with ser_lock:
            s = ser
        if s is None:
            time.sleep(0.2); continue
        try:
            data = s.read(512)
        except Exception as e:
            log(f"serial read error ({e}); reconnecting")
            try: s.close()
            except Exception: pass
            with ser_lock:
                ser = None
            drop_all_clients()      # force clients to re-handshake against the fresh device
            open_serial()
            continue
        if data:
            broadcast(data)

def write_frame(frame):
    with ser_lock:
        if ser is not None:
            try: ser.write(frame)
            except Exception as e: log(f"serial write error ({e})")

def handle_client(conn, addr):
    log(f"client connected: {addr}")
    buf = bytearray()
    hs = {"held": False, "timer": None}

    def release_hs():
        if hs["timer"]:
            hs["timer"].cancel(); hs["timer"] = None
        if hs["held"]:
            hs["held"] = False
            try: handshake_lock.release()
            except RuntimeError: pass

    def acquire_hs():
        # serialize opening handshakes: take the lock before this client's first
        # frame (its wantConfig), auto-release after a short window so its config
        # stream completes before the next client is let through.
        handshake_lock.acquire()
        hs["held"] = True
        hs["timer"] = threading.Timer(HANDSHAKE_WINDOW, release_hs)
        hs["timer"].daemon = True
        hs["timer"].start()

    try:
        while True:
            chunk = conn.recv(512)
            if not chunk:
                break
            buf += chunk
            # Extract and write only COMPLETE frames, atomically.
            while True:
                # locate frame start magic
                i = 0
                while i + 1 < len(buf) and not (buf[i] == START1 and buf[i + 1] == START2):
                    i += 1
                if i > 0:
                    del buf[:i]                       # drop garbage before magic
                if len(buf) < 4:
                    break                             # need full 4-byte header
                if not (buf[0] == START1 and buf[1] == START2):
                    del buf[:1]; continue             # lone trailing byte, resync
                ln = (buf[2] << 8) | buf[3]
                if ln > MAX_FRAME:                    # desync / bad length -> skip this magic
                    del buf[:2]; continue
                if len(buf) < 4 + ln:
                    break                             # frame not fully arrived yet
                if not hs["held"] and not hs.get("done"):
                    hs["done"] = True                 # first frame == wantConfig: take handshake turn
                    acquire_hs()
                write_frame(bytes(buf[:4 + ln]))
                del buf[:4 + ln]
    except Exception as e:
        log(f"client {addr} error: {e}")
    finally:
        release_hs()
        with clients_lock:
            clients.discard(conn)
        try: conn.close()
        except Exception: pass
        log(f"client disconnected: {addr}")

def main():
    open_serial()
    threading.Thread(target=serial_reader, daemon=True).start()
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", TCP_PORT))
    srv.listen(8)
    log(f"=== bridge live: Meshtastic TCP API on 0.0.0.0:{TCP_PORT} (auto-reconnect + frame-safe) ===")
    while True:
        conn, addr = srv.accept()
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        with clients_lock:
            clients.add(conn)
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    main()
