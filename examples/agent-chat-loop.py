#!/usr/bin/env python3
"""
Minimal AGENT CHAT LOOP over the Meshtastic mesh — the cross-communication pattern
in ~40 lines: listen for messages, decide, reply. Two people who each run something
like this (or a real agent) can converse entirely over LoRa, no internet.

This demo answers "ping" with "pong from <me>" and ignores everything else, so it's a
harmless mesh presence check — it won't spam the channel. **Replace `respond()` with
your own logic** (call an LLM, run a command, look something up) to make it a real
agent on the mesh.

Usage:
  agent-chat-loop.py [--channel N] [--target T] [--broadcast]
    --target     tcp / tcp:HOST (via the bridge) | /dev/cu.usbmodem* | serial
    --broadcast  reply on the channel (everyone sees it) instead of DMing the sender
"""
import time, argparse, glob, socket


def respond(text, sender):
    """Return a reply string, or None to stay quiet. >>> put your agent logic here <<<"""
    if text.strip().lower().startswith("ping"):
        return "pong"
    return None


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


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--channel", type=int, default=0)
    p.add_argument("--target", default=default_target())
    p.add_argument("--broadcast", action="store_true")
    a = p.parse_args()

    from pubsub import pub
    iface = connect(a.target)
    me = iface.myInfo.my_node_num

    def on_message(packet, interface):
        d = packet.get("decoded", {}) or {}
        if d.get("portnum") != "TEXT_MESSAGE_APP" or packet.get("from") == me:
            return  # ignore non-text and our own messages
        sender = packet.get("fromId")
        text = d.get("text", "")
        print(f"<< {sender}: {text}")
        reply = respond(text, sender)
        if reply:
            dest = "^all" if a.broadcast else sender   # DM the sender by default
            iface.sendText(reply, destinationId=dest, channelIndex=a.channel)
            print(f">> {dest}: {reply}")

    pub.subscribe(on_message, "meshtastic.receive")
    print(f"agent chat loop live on channel {a.channel} (node !{me:08x}). Ctrl-C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        iface.close()


if __name__ == "__main__":
    main()
