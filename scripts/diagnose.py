#!/usr/bin/env python3
"""L1/L2/L3/L4 — Connect to a Meshtastic node and dump the facts that matter.

Prints firmware, region, modem preset, tx_enabled, hop_limit, the channel list
(role / name / psk length), and node count. Read-only: mutates nothing.

A hard signal.alarm() timeout guarantees this can never hang forever -- a silent
serial API (classic bad-dev-build symptom) exits with code 99 instead of blocking.

Usage:
    python diagnose.py [/dev/cu.usbmodemXXXX]
Run with the venv python that has `meshtastic`, e.g.
    ~/.local/pipx/venvs/meshtastic/bin/python diagnose.py
"""
import base64
import glob
import signal
import sys
import time


def pick_port():
    if len(sys.argv) > 1:
        return sys.argv[1]
    ports = sorted(glob.glob("/dev/cu.usbmodem*"))
    if not ports:
        print("FAIL: no /dev/cu.usbmodem* port. Run detect.sh (L0).")
        sys.exit(2)
    return ports[0]


def on_timeout(signum, frame):
    print("\n!! TIMEOUT: serial API never answered.")
    print("   The node enumerates but is silent -- typically a bad/half-installed")
    print("   firmware (often a dev nightly). Fix: flash stable (flash-stable.sh).")
    sys.exit(99)


def main():
    port = pick_port()
    signal.signal(signal.SIGALRM, on_timeout)
    signal.alarm(40)

    import meshtastic.serial_interface as si
    from meshtastic.protobuf import config_pb2

    print(f"Connecting to {port} ...")
    iface = si.SerialInterface(port)
    signal.alarm(0)  # connected; drop the watchdog

    mi, md = iface.myInfo, iface.metadata
    lc = iface.localNode.localConfig
    lora = lc.lora
    region = config_pb2.Config.LoRaConfig.RegionCode.Name(lora.region)
    preset = config_pb2.Config.LoRaConfig.ModemPreset.Name(lora.modem_preset)

    print("\n== DEVICE ==")
    print(f"  firmware     : {getattr(md, 'firmware_version', '?')}")
    print(f"  my node num  : {getattr(mi, 'my_node_num', '?')}")
    print(f"  reboot count : {getattr(mi, 'reboot_count', '?')}")

    print("\n== LORA / REGION ==")
    print(f"  region       : {region} ({lora.region})"
          + ("   <-- UNSET = radio will NOT TX/RX!" if region == "UNSET" else ""))
    print(f"  modem_preset : {preset}  (use_preset={lora.use_preset})")
    print(f"  tx_enabled   : {lora.tx_enabled}")
    print(f"  tx_power     : {lora.tx_power} dBm")
    print(f"  hop_limit    : {lora.hop_limit}")
    print(f"  freq_slot    : {lora.channel_num}")

    print("\n== CHANNELS ==")
    node = iface.localNode
    for idx in range(8):
        ch = node.getChannelByChannelIndex(idx)
        if ch is None or ch.role == 0:  # 0 = DISABLED
            continue
        role = {1: "PRIMARY", 2: "SECONDARY"}.get(ch.role, str(ch.role))
        s = ch.settings
        psk = s.psk or b""
        tag = " (default public)" if psk == b"\x01" else ""
        b64 = base64.b64encode(psk).decode()
        print(f"  [{idx}] {role:9} name='{s.name or '(default LongFast)'}' "
              f"psk_len={len(psk)}{tag} psk_b64={b64[:16]}{'...' if len(b64) > 16 else ''}")

    nodes = iface.nodes or {}
    print(f"\n== NODES ==\n  total in DB: {len(nodes)}"
          + ("   (empty right after a reflash is NORMAL -- run monitor.py)" if len(nodes) <= 1 else ""))
    now = time.time()
    for nid, n in sorted(nodes.items(), key=lambda kv: kv[1].get("lastHeard", 0) or 0, reverse=True)[:15]:
        u = n.get("user", {})
        lh = n.get("lastHeard")
        ago = "never" if not lh else f"{int(now - lh)}s"
        print(f"    {str(u.get('shortName', '?')):8} hops={n.get('hopsAway', '?')} "
              f"snr={n.get('snr', '?')} lastHeard={ago}  {u.get('longName', '')}")

    iface.close()
    print("\nOK: node is alive and answering (L1 pass).")


if __name__ == "__main__":
    main()
