#!/usr/bin/env python3
"""L2/L3 — Assert a node's config is sane for joining the public mesh.

Checks (read-only, mutates nothing):
  - region  != UNSET
  - modem_preset == LONG_FAST
  - tx_enabled == True
  - a PRIMARY channel named 'LongFast' exists

Prints PASS/FAIL per check and exits non-zero if any FAIL.

Usage: python assert-config.py [/dev/cu.usbmodemXXXX]
"""
import glob
import signal
import sys

PASS, FAIL = "PASS", "FAIL"


def pick_port():
    if len(sys.argv) > 1:
        return sys.argv[1]
    ports = sorted(glob.glob("/dev/cu.usbmodem*"))
    if not ports:
        print("FAIL: no /dev/cu.usbmodem* port (run detect.sh).")
        sys.exit(2)
    return ports[0]


def on_timeout(signum, frame):
    print("!! TIMEOUT: serial API silent -> flash stable (flash-stable.sh).")
    sys.exit(99)


def main():
    port = pick_port()
    signal.signal(signal.SIGALRM, on_timeout)
    signal.alarm(40)

    import meshtastic.serial_interface as si
    from meshtastic.protobuf import config_pb2

    iface = si.SerialInterface(port)
    signal.alarm(0)

    lora = iface.localNode.localConfig.lora
    region = config_pb2.Config.LoRaConfig.RegionCode.Name(lora.region)
    preset = config_pb2.Config.LoRaConfig.ModemPreset.Name(lora.modem_preset)

    results = []

    def check(name, ok, detail):
        results.append(ok)
        print(f"  [{PASS if ok else FAIL}] {name}: {detail}")

    check("region set", region != "UNSET",
          f"{region}" + ("" if region != "UNSET" else "  <-- radio will NOT TX/RX"))
    check("modem preset", preset == "LONG_FAST", preset)
    check("tx enabled", bool(lora.tx_enabled), str(lora.tx_enabled))

    node = iface.localNode
    primary_name = None
    for idx in range(8):
        ch = node.getChannelByChannelIndex(idx)
        if ch is not None and ch.role == 1:  # PRIMARY
            primary_name = ch.settings.name or "LongFast"  # blank name == default LongFast
            break
    check("primary = LongFast", primary_name == "LongFast",
          primary_name if primary_name is not None else "(no primary channel!)")

    iface.close()
    print("\n" + ("ALL PASS -- node is configured to see the public mesh."
                  if all(results) else "FAILURES above -- fix before expecting nodes."))
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
