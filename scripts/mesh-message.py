#!/usr/bin/env python3
"""
Send and receive text over the Meshtastic mesh — the core of agent-to-agent and
agent-to-people communication. Output is JSON so an AI agent can drive it directly.

Meshtastic messages are end-to-end encrypted per channel and relayed hop-to-hop
over LoRa: no internet, SIM, or infrastructure. A message on the default public
"LongFast" channel reaches every node in radio range (and their agents); a private
channel reaches only those who share its key.

Usage:
  mesh-message.py send "your text" [--ch N] [--to !nodeid] [--ack] [--target T]
  mesh-message.py listen [--seconds N] [--target T]        # JSON line per message

TARGET: "tcp"/"tcp:HOST" (through the serial-tcp bridge, so it doesn't fight other
        clients for the USB port), a /dev/cu.usbmodem* path, or "serial".
        Default: the bridge on 127.0.0.1:4403 if it's up, else the first USB node.
"""
import sys, json, time, glob, socket, argparse

def default_target():
    s = socket.socket(); s.settimeout(0.3)
    try:
        s.connect(("127.0.0.1", 4403)); s.close(); return "tcp:127.0.0.1"
    except Exception:
        return "serial"

def connect(target):
    if target.startswith("tcp"):
        import meshtastic.tcp_interface as ti
        host = target.split(":", 1)[1] if ":" in target else "127.0.0.1"
        return ti.TCPInterface(host)
    import meshtastic.serial_interface as si
    dev = None if target in ("serial", "") else target
    if dev is None:
        m = sorted(glob.glob("/dev/cu.usbmodem*")); dev = m[0] if m else None
    return si.SerialInterface(dev)

def cmd_send(a):
    i = connect(a.target)
    dest = a.to or "^all"
    i.sendText(a.text, destinationId=dest, wantAck=a.ack, channelIndex=a.ch)
    time.sleep(2)  # give the radio time to actually transmit before we close
    print(json.dumps({"ok": True, "sent": a.text, "channel": a.ch,
                      "to": dest, "wantAck": a.ack}))
    i.close()

def cmd_listen(a):
    from pubsub import pub
    i = connect(a.target)
    me = i.myInfo.my_node_num
    def onrx(packet, interface):
        d = packet.get("decoded", {}) or {}
        if d.get("portnum") != "TEXT_MESSAGE_APP":
            return
        print(json.dumps({
            "ts": int(time.time()),
            "from": packet.get("fromId"),
            "from_self": packet.get("from") == me,
            "channel": packet.get("channel", 0),
            "snr": packet.get("rxSnr"),
            "hops_away": packet.get("hopLimit"),
            "text": d.get("text", ""),
        }), flush=True)
    pub.subscribe(onrx, "meshtastic.receive")
    end = time.time() + a.seconds
    while time.time() < end:
        time.sleep(0.5)
    i.close()

def main():
    p = argparse.ArgumentParser(description="Meshtastic messaging (JSON I/O)")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("send"); s.add_argument("text")
    s.add_argument("--ch", type=int, default=0); s.add_argument("--to", default=None)
    s.add_argument("--ack", action="store_true"); s.add_argument("--target", default=default_target())
    s.set_defaults(fn=cmd_send)
    l = sub.add_parser("listen"); l.add_argument("--seconds", type=int, default=3600)
    l.add_argument("--target", default=default_target()); l.set_defaults(fn=cmd_listen)
    a = p.parse_args(); a.fn(a)

if __name__ == "__main__":
    main()
