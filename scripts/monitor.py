#!/usr/bin/env python3
"""L4 — Watch the mesh come alive.

Prints every received packet (fromId / portnum / snr / rssi / hops) and, every
60s, a running node table (shortName / hops / snr / lastHeard-ago). This is how
you prove "empty node list right after a reflash is just NORMAL repopulation."

Runs until Ctrl-C, or for a fixed window with --seconds N.

Usage:
    python monitor.py [/dev/cu.usbmodemXXXX] [--seconds 300]

Note: snr/rssi = None means the packet arrived relayed/multi-hop (or via MQTT)
rather than direct RF -- still proof the mesh is reaching you.
"""
import glob
import sys
import time


def parse_args():
    port, seconds = None, None
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--seconds":
            seconds = int(args[i + 1]); i += 2
        else:
            port = args[i]; i += 1
    if port is None:
        ports = sorted(glob.glob("/dev/cu.usbmodem*"))
        if not ports:
            print("FAIL: no /dev/cu.usbmodem* port (run detect.sh).")
            sys.exit(2)
        port = ports[0]
    return port, seconds


def main():
    port, seconds = parse_args()
    import meshtastic.serial_interface as si
    from pubsub import pub

    count = {"n": 0}

    def on_rx(packet, interface):
        count["n"] += 1
        d = packet.get("decoded", {})
        print(f"  RX from={packet.get('fromId')} type={d.get('portnum')} "
              f"snr={packet.get('rxSnr')} rssi={packet.get('rxRssi')} "
              f"hops={packet.get('hopLimit')}")

    pub.subscribe(on_rx, "meshtastic.receive")
    iface = si.SerialInterface(port)
    print(f"Listening on {port}"
          + (f" for {seconds}s" if seconds else " (Ctrl-C to stop)") + " ...")

    start = time.time()
    last_table = 0.0
    try:
        while True:
            time.sleep(1)
            now = time.time()
            if now - last_table >= 60:
                last_table = now
                nodes = iface.nodes or {}
                print(f"\n--- node table ({len(nodes)} nodes, {count['n']} packets so far) ---")
                for nid, n in sorted(nodes.items(),
                                     key=lambda kv: kv[1].get("lastHeard", 0) or 0,
                                     reverse=True)[:20]:
                    u = n.get("user", {})
                    lh = n.get("lastHeard")
                    ago = "never" if not lh else f"{int(now - lh)}s"
                    print(f"    {str(u.get('shortName', '?')):8} "
                          f"hops={n.get('hopsAway', '?')} snr={n.get('snr', '?')} "
                          f"lastHeard={ago}")
                print("--- (empty/small right after a reflash is NORMAL) ---\n")
            if seconds and now - start >= seconds:
                break
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        iface.close()
        print(f"done: {count['n']} packets, {len(iface.nodes or {})} nodes in DB.")


if __name__ == "__main__":
    main()
