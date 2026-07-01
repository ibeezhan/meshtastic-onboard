---
name: meshtastic-onboard
description: Connect, debug, set up, report on, and share a Meshtastic node (especially the SenseCAP T1000-E) over USB on macOS. Use when the user can't see other nodes, wants to flash firmware, recover a node stuck after a fresh/dev install, verify region/channel config, join a community mesh (e.g. Lisboa-e-Arredores), get a status report of connected nodes / messages / signal, or expose the node on the LAN (phone app over TCP or the browser web client) without Bluetooth. Walks a layered L0–L5 diagnosis and narrates the *why* at each step.
---

# Meshtastic onboarding & debugging (openclaw → meshtastic)

A guided runbook for getting a Meshtastic node — built and tested on the **Seeed SenseCAP T1000-E** (nRF52840) on **macOS** — from "plugged in but I see nothing" to "live on the mesh." Diagnose **bottom-up**: never debug layer N while layer N-1 is broken. Narrate the teaching aside out loud — the goal is that a newcomer *learns the stack*, not just gets unblocked.

Helper scripts live in `scripts/`. They auto-find a Python with the `meshtastic` lib (prefers `~/.local/pipx/venvs/meshtastic/bin/python`). Install prereqs once:

```
pipx install meshtastic
pipx install adafruit-nrfutil
```

### Scripts inventory (`scripts/`)

| Script | Purpose | Layer |
|---|---|---|
| `detect.sh` | List serial ports + USB tree; flag charge-only cable | L0 |
| `diagnose.py` | Connect (hard timeout) → fw/region/preset/tx/channels/nodes | L1–L4 |
| `assert-config.py` | PASS/FAIL region≠UNSET, preset, tx, primary=LongFast (read-only) | L2/L3 |
| `report.py` | **Full status report**: device, channels, node table, live messages, packet activity, signal quality | any |
| `monitor.py` | Live packet stream + node table growth; `--seconds N` | L4 |
| `flash-stable.sh` | Download + MD5-verify + serial-DFU flash of latest stable | recovery |
| `import-channel.sh` | `meshtastic --seturl` wrapper for a community channel | L3 |
| `serial-tcp-bridge.py` | Own the USB port, re-serve as Meshtastic **TCP** on :4403 (auto-reconnect, frame-safe multi-client) | LAN |
| `lan-dashboard.py` | Lightweight USB-backed **web dashboard** on the LAN | LAN |

`report.py` and the LAN scripts can talk over **TCP through the bridge** (so they don't fight the web client for the USB port) — pass `tcp` or `tcp:HOST`.

---

## L0 — Is the node physically on the USB bus?

**Check:**
```
bash scripts/detect.sh
```
This lists `/dev/cu.usbmodem*` and greps the `ioreg` USB tree for a Seeed/Nordic device.

**Interpret:**
- A `/dev/cu.usbmodem*` port appears → good, go to L1.
- Nothing at all → the host can't see the radio.

**Teaching aside / #1 gotcha:** On macOS the single most common cause of "nothing shows up" is a **charge-only USB cable**. The node charges fine (LED, battery) so it *looks* connected, but the cable has no data lines and never enumerates. **Swap to a known-good data cable before anything else.** Second cause: the device is asleep (the T1000-E sleeps hard) — wake it with the button.

---

## L0b — What *mode* is it in? (and the descriptor trap)

**Check:**
```
ioreg -p IOUSB -l | grep -i "USB Product Name" | grep -i T1000
```

**THE BIG TRAP:** the T1000-E reports its USB product name as **`T1000_E_BOOT` even when the application firmware is running** — not only in the bootloader. **Never infer "stuck in bootloader" from that string.** The *only* reliable liveness signal is whether the Meshtastic serial API answers (L1). We burned a lot of time treating `_BOOT` as "bootloader"; don't repeat it.

A genuine UF2 bootloader also (sometimes) mounts a `T1000-E` mass-storage drive — but only after the physical **hold-button + double-tap-the-magnetic-cable** gesture. Absence of that drive tells you nothing on its own.

---

## L1 — Liveness: does the API actually answer?

**Check:**
```
python scripts/diagnose.py            # or: python scripts/diagnose.py /dev/cu.usbmodemXXXX
```
(`diagnose.py` opens the port with a hard `signal.alarm` timeout so it can never hang forever.)

**Interpret:**
- Dumps firmware/region/channels/nodes → the node is **alive**; go to L2.
- Times out with no response → the serial API is **silent**. This is the decision point for a reflash.

**Teaching aside:** A silent serial API on a node that enumerates is the classic symptom of a **bad/half-installed firmware** — very common after flashing a **dev nightly**. The fix is to flash a **stable** release. See "Flashing" below.

---

## L2 — Radio config (region is the #1 silent killer)

`diagnose.py` already printed these. Or assert them:
```
python scripts/assert-config.py
```

**Must be true to see anyone:**
- `region` is set (e.g. **EU_868** for Portugal) and **not `UNSET`**. UNSET = the radio legally refuses to TX/RX → you will see *nothing*, with no error.
- `modem_preset` matches the local mesh (**LONG_FAST** is the near-universal default).
- `tx_enabled = true`, sane `hop_limit` (default 3–5).

**Teaching aside:** A fresh flash can leave `region = UNSET`. It's the most common "everything looks fine but no nodes" cause after L1 passes.

---

## L3 — Channels & crypto

**Check:** the channel list from `diagnose.py`.

**Interpret:**
- `[0] PRIMARY LongFast` with `psk = AQ==` → the **default public key**: the global public channel, and how you're *discovered*. Keep it.
- A `SECONDARY` with a 32-byte PSK → a community channel (e.g. **`LX e Arredores`** = Lisboa-e-Arredores).

**Teaching aside — the preset/channel confusion:** Channels are **AES keys layered on the *same* RF transmission** as LongFast. They share the preset and frequency. So **switching the modem preset does NOT help you "hear" a community channel** — if a node is on LongFast/EU_868, you already receive its packets; the channel key only decides which ones you can *decrypt*. You change preset only to find nets that are deliberately on a **different preset** (a separate RF configuration). To join a community channel you need its exact **name + PSK**, normally imported from an official share URL:
```
bash scripts/import-channel.sh "https://meshtastic.org/e/#..."
```
**Never invent a PSK or a share URL** — get the real one from the community.

---

## L4 — NodeDB & time ("empty is normal")

**Check:** node count from `diagnose.py`; then watch it grow:
```
python scripts/monitor.py            # Ctrl-C to stop, or: python scripts/monitor.py --seconds 300
```

**Teaching aside:** A **reflash or factory reset wipes the NodeDB**, so the list starts empty *and that is expected*. Nodes repopulate as they rebroadcast **NodeInfo** — anywhere from a few minutes to a few hours. Don't conclude "broken" from an empty list right after a flash; let `monitor.py` run and watch packets arrive. Packets with `snr/rssi = None` arrived relayed/multi-hop (or via MQTT) rather than direct RF — still proof the mesh is reaching you.

---

## L5 — RF environment

If L1–L4 pass but you still hear nobody after a sustained `monitor.py` run:
- Antenna attached? (Never TX without one.)
- Deep indoors / basement? 868 MHz wants line-of-sight; move to a window or outdoors.
- Genuinely out of range — check community maps for the nearest active node and confirm `monitor.py` shows direct-RF packets (non-null SNR/RSSI) vs only relayed ones.

---

## Flashing stable (recovery) — serial DFU, no drive, no double-tap

When L1 says the API is silent (bad dev build), flash the latest **stable**:
```
bash scripts/flash-stable.sh         # downloads, MD5-verifies, flashes via serial DFU
```

What it does and the gotchas baked in:
- Pulls the latest **stable** GitHub release, grabs `firmware-nrf52840-<ver>.zip`, extracts the **`tracker-t1000-e` OTA package** (`...-ota.zip`), the UF2, and the matching **S140 erase** UF2; MD5-verifies the UF2 against the bundled `.mt.json`.
- Flashes over the bootloader's CDC with:
  ```
  adafruit-nrfutil dfu serial -pkg <ota.zip> -p <port> -b 115200 -t 1200
  ```
  **The `-t 1200` (1200-baud touch) is required** — it wakes the bootloader's serial-DFU listener. Without it you get `No data received on serial port`.
- This route needs **no UF2 drive and no double-tap gesture** — far smoother than drag-drop.

**If you must drag-drop a UF2 instead** (DFU drive `/Volumes/T1000-E` mounted via hold-button + double-tap-magnetic-cable): **do not use `cp`** — on macOS it fails with `could not copy extended attributes: Device not configured` and **truncates the write** (the drive reboots out from under it). Use a raw copy:
```
cat firmware-tracker-t1000-e-<ver>.uf2 > /Volumes/T1000-E/fw.uf2
```

After flashing, re-run `diagnose.py`. Region/channels may need re-applying (re-confirm **EU_868 + LongFast**, re-import the community channel URL). A wiped NodeDB refilling slowly is normal (L4).

---

## Reporting & monitoring — what a good status report includes

Run a full report any time (works over USB, or over TCP through the bridge so it
doesn't fight the web client for the port):
```
python scripts/report.py                 # default: tcp:127.0.0.1 via the bridge, 25s listen
python scripts/report.py serial 60       # over USB instead, listen 60s
python scripts/report.py tcp:192.168.1.50 30   # 192.168.1.50 = example LAN IP
```

A complete report answers *"am I healthy, who can I hear, and is traffic flowing?"* — include:
- **Device & firmware** — long/short name + node id, firmware version.
- **Radio config** — region / preset, `tx_enabled`, `hop_limit`.
- **Health** — battery %, voltage, **air-util-TX** and **channel-utilization** (near 0.0 = quiet air / sparse mesh; high = congested).
- **Channels** — role + name + whether encrypted (default-key vs community key).
- **Node table** — for every node: name, id, **hops** (0 = direct RF neighbor), **SNR**, battery, **last-heard age**; tag self / direct.
- **Live messages** — text messages overheard during the listen window. (Meshtastic keeps **no host-side history**, so only what arrives while listening shows up — say so.)
- **Direct-RF neighbors heard in-window** — nodes received with a non-null SNR (true radio neighbors vs relayed).
- **Packet activity by type** — TELEMETRY / POSITION / NODEINFO / TEXT counts, a quick pulse of what's on air.

**Reading signal:** `hops=0` + a real `snr` = a direct neighbor. `snr/rssi = None` = relayed/multi-hop (or MQTT), not heard directly. LONG_FAST decodes down to roughly **−20 dB SNR**, so −17 dB is a real but *faint* link — expect it to be intermittent.

`monitor.py` is the streaming companion: it prints each packet and reprints the node table every 60s, so you can watch the NodeDB fill after a flash.

---

## LAN access (no Bluetooth): phone app + browser web client

nRF52 boards have **no WiFi**, so they can't host the web UI or join the LAN
themselves — only USB serial and (flaky) BLE. To get stable LAN access without
Bluetooth, bridge the USB link. See `lan/` in the project:

```
./lan/start-lan-stack.sh      # bridge :4403  +  http-proxy :8080  +  web client :3000
./lan/stop-lan-stack.sh
```

- **Phone/desktop app (simplest):** Meshtastic app → *New connection* → **IP/TCP** →
  `<LAN_IP>` port **4403**. Full map/messaging/config, no BLE.
- **Browser web client:** open `http://<LAN_IP>:3000`. It **auto-connects** to the
  proxy via the injected `autoconnect.js` (override `?proxy=host:port`, disable
  `?noauto`). Manual: HTTP tab → type `<LAN_IP>:8080` → Connect (no TLS toggle in
  this build — scheme is inferred).
- **Lightweight dashboard alternative:** `python scripts/lan-dashboard.py` serves a
  minimal USB-backed status page on `:8765` (no proxy/web-client build needed).

Architecture: `node → serial-tcp-bridge (:4403) → { app direct | http-proxy (:8080) → web (:3000) }`.
The bridge multiplexes (app + web + tools at once) and auto-reopens the serial port
when the node is unplugged/moved (USB re-enumerates → `Errno 6`). **Only one process
may own the USB port** — use the bridge as that owner; point everything else at TCP.

---

## Known-good reference (T1000-E, Lisbon)

```
firmware : latest stable (tracker-t1000-e)
region   : EU_868
preset   : LONG_FAST   (use_preset=true)
tx       : enabled, tx_power 27 dBm, hop_limit 5
channels : [0] PRIMARY  LongFast        psk=AQ== (default public)
           [1] SECONDARY "LX e Arredores"  32-byte AES256 (import from official URL)
```
