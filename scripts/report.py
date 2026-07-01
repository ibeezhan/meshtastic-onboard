#!/usr/bin/env python3
"""
Comprehensive status report for a Meshtastic node: device/firmware, radio config,
channels, the node list (who you can hear, how well), live messages, and packet
activity. Works over the serial USB link OR over TCP (e.g. through the bridge, so
it doesn't fight the web client for the USB port).

Usage:
  report.py [TARGET] [LISTEN_SECS]
    TARGET      "tcp" or "tcp:HOST" (default 127.0.0.1:4403 via the bridge),
                or a serial device path like /dev/cu.usbmodemXXXX,
                or "serial" to auto-pick the first /dev/cu.usbmodem*.
    LISTEN_SECS  how long to watch for live messages/packets (default 25).

Note: Meshtastic does not store message history on the host, so "messages"
below are only those overheard during the listen window.
"""
import sys, glob, time
from collections import Counter
from pubsub import pub

TARGET = sys.argv[1] if len(sys.argv) > 1 else "tcp:127.0.0.1"
LISTEN = int(sys.argv[2]) if len(sys.argv) > 2 else 25

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

def ago(lh, now):
    if not lh: return "never"
    d = now - lh
    return f"{int(d)}s" if d < 90 else (f"{int(d/60)}m" if d < 5400 else f"{int(d/3600)}h")

messages, pkt_types, direct = [], Counter(), {}
MY = None

def onrx(packet, interface):
    d = packet.get("decoded", {}) or {}
    pn = d.get("portnum", "?"); pkt_types[pn] += 1
    if pn == "TEXT_MESSAGE_APP":
        messages.append((time.strftime("%H:%M:%S"), packet.get("fromId"),
                         packet.get("channel", 0), d.get("text", "")))
    if packet.get("from") != MY and packet.get("rxSnr") is not None:
        direct[packet.get("from")] = (packet.get("rxSnr"), packet.get("rxRssi"))

pub.subscribe(onrx, "meshtastic.receive")

i = connect(TARGET)
MY = i.myInfo.my_node_num
from meshtastic.protobuf import config_pb2
lora = i.localNode.localConfig.lora
now = time.time()
nodes = i.nodes or {}
me = nodes.get(f"!{MY:08x}", {}) or next((n for n in nodes.values() if n.get("num") == MY), {})
mm = me.get("deviceMetrics", {}) or {}

print("=" * 66)
print("MESHTASTIC NODE REPORT")
print("=" * 66)
print(f"  node        : {me.get('user',{}).get('longName','?')}  ({me.get('user',{}).get('shortName','?')})  !{MY:08x}")
print(f"  firmware    : {getattr(i.metadata,'firmware_version','?')}")
print(f"  region/preset: {config_pb2.Config.LoRaConfig.RegionCode.Name(lora.region)} / {config_pb2.Config.LoRaConfig.ModemPreset.Name(lora.modem_preset)}")
print(f"  tx_enabled  : {lora.tx_enabled}   hop_limit: {lora.hop_limit}")
print(f"  battery     : {mm.get('batteryLevel','?')}%   voltage: {mm.get('voltage','?')}V")
print(f"  air util TX : {mm.get('airUtilTx','?')}   channel util: {mm.get('channelUtilization','?')}")
print("  channels    :")
for idx in range(8):
    ch = i.localNode.getChannelByChannelIndex(idx)
    if ch is None or ch.role == 0: continue
    role = {1: "PRIMARY", 2: "SECONDARY"}.get(ch.role, ch.role)
    enc = "encrypted" if len(ch.settings.psk) > 1 else "default-key"
    print(f"      [{idx}] {role:9} {ch.settings.name or 'LongFast':14} ({enc})")

print("-" * 66)
direct_n = [n for n in nodes.values() if n.get("hopsAway") == 0 and n.get("num") != MY]
print(f"NODES: {len(nodes)} total   |   {len(direct_n)} direct (hops=0)   |   self=1")
print(f"  {'name':10}{'id':12}{'hops':5}{'snr':7}{'batt':6}{'last heard'}")
for num, n in sorted(nodes.items(), key=lambda kv: (kv[1].get("lastHeard") or 0), reverse=True):
    u = n.get("user", {}) or {}; dm = n.get("deviceMetrics", {}) or {}
    tag = " *self" if n.get("num") == MY else (" <direct" if n.get("hopsAway") == 0 else "")
    print(f"  {(u.get('shortName') or '?'):10}{('!%08x'%n['num']) if n.get('num') else '?':12}"
          f"{str(n.get('hopsAway','?')):5}{str(n.get('snr','?')):7}{str(dm.get('batteryLevel','?'))+'%':6}"
          f"{ago(n.get('lastHeard'), now)}{tag}")

print("-" * 66)
print(f"LISTENING {LISTEN}s for live messages & packets ...")
t = time.time()
while time.time() - t < LISTEN:
    time.sleep(1)

print("-" * 66)
print(f"MESSAGES received in window: {len(messages)}")
for ts, frm, chan, txt in messages:
    print(f"  [{ts}] ch{chan} {frm}: {txt}")
print(f"DIRECT-RF neighbors heard in window: {len(direct)}")
for num, (snr, rssi) in sorted(direct.items(), key=lambda kv: -(kv[1][0] or -999)):
    nm = (nodes.get(f'!{num:08x}', {}) or {}).get('user', {}).get('shortName', '?')
    print(f"  {nm:10} !{num:08x}  snr={snr} rssi={rssi}")
print(f"PACKET activity by type: {dict(pkt_types)}")
print("=" * 66)
i.close()
