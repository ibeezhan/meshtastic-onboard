# meshtastic-onboard

**Get a [Meshtastic](https://meshtastic.org) node from "plugged in but I see nothing" to "live on the mesh" — with an agent that narrates *why* at every step.**

A [Claude Code](https://docs.anthropic.com/en/docs/claude-code) **skill** (and a set of standalone scripts) for connecting, debugging, flashing, configuring, **reporting on**, and **LAN-sharing** a Meshtastic node over USB. Built and battle-tested on the **Seeed SenseCAP T1000-E** (nRF52840) on macOS, but the methodology is general.

It exists because the first-run experience of a cheap LoRa mesh node is full of silent failure modes — a charge-only cable, a bootloader that lies about its state, a dev-nightly with a dead serial port, a region left `UNSET`, an empty node list that's actually *normal*. This skill encodes the fixes as a **layered, teach-as-you-go runbook** so a newcomer learns the stack instead of just getting unblocked.

---

## What you get

- 🩺 **Layered diagnosis (L0–L5)** — isolate the problem bottom-up: USB link → device liveness → radio config → channels/crypto → node DB → RF. Never debug layer N while N‑1 is broken.
- ⚡ **One-command recovery flash** — latest **stable** firmware via serial DFU (no fragile drag-drop, no button gymnastics).
- 📋 **Status reports** — node table (who you hear, how well), live messages, signal quality, channel utilization, packet activity.
- 📡 **LAN access without Bluetooth** — bridge the USB link so the phone app (TCP) *and* the official browser web client (map/messaging/config) work over your LAN, with one-click auto-connect.
- 🧠 **Agent-friendly** — see [`AGENTS.md`](AGENTS.md) for the decision tree and script contracts an LLM agent can follow.

---

## Quickstart

### Prereqs
```bash
pipx install meshtastic          # the Meshtastic Python CLI + lib
pipx install adafruit-nrfutil    # only needed for flashing nRF52 boards
```

### Use as a Claude Code skill
Clone into your skills directory — the repo root *is* the skill:
```bash
git clone https://github.com/<you>/meshtastic-onboard ~/.claude/skills/meshtastic-onboard
```
Then just ask: *"my meshtastic node can't see any nodes"*, *"flash stable firmware"*, *"give me a node report"*, *"put the node on my LAN"* — the skill loads automatically.

### Use the scripts standalone
```bash
bash scripts/detect.sh                 # L0: is the node on the USB bus?
python scripts/diagnose.py             # L1–L4: fw / region / channels / nodes
python scripts/report.py serial 30     # full status report (30s message listen)
python scripts/monitor.py --seconds 300  # watch packets & the node list grow
bash scripts/flash-stable.sh           # recovery: flash latest stable
```

---

## The workflow (L0–L5)

| Layer | Question | Tool | Classic gotcha |
|---|---|---|---|
| **L0** | Is it on the USB bus? | `detect.sh` | **Charge-only cable** — charges fine, no data lines, never enumerates |
| **L0b** | What mode is it in? | `ioreg` | The T1000-E reports `..._BOOT` **even when the app is running** — never infer "bootloader" from it |
| **L1** | Does the API answer? | `diagnose.py` | A silent serial API on a node that enumerates = **bad dev-nightly** → flash stable |
| **L2** | Radio config sane? | `assert-config.py` | `region = UNSET` → radio legally won't TX/RX → **you see nothing, no error** |
| **L3** | Channels & crypto | `diagnose.py` | Channels are AES keys on the **same RF** as LongFast — switching *preset* won't help you hear a community channel |
| **L4** | Node DB & time | `monitor.py` | A reflash **wipes the node DB**; empty-then-slowly-refilling is **normal** |
| **L5** | RF environment | `monitor.py` | Antenna? Indoors? 868 MHz wants line-of-sight — a windowsill beats a drawer |

Full narrative with teaching asides: [`SKILL.md`](SKILL.md).

---

## Example: a status report

`python scripts/report.py` (sample output — **all data below is fabricated**):

```
==================================================================
MESHTASTIC NODE REPORT
==================================================================
  node         : Example Node  (EXMP)  !a1b2c3d4
  firmware     : 2.7.x (tracker-t1000-e)
  region/preset: EU_868 / LONG_FAST     tx: enabled   hop_limit: 5
  battery      : 87%   3.98V
  air util TX  : 0.041   channel util: 0.6
  channels     : [0] PRIMARY   LongFast     (default-key)
                 [1] SECONDARY  MyRegion_Ch  (encrypted)
------------------------------------------------------------------
NODES: 4 total   |   2 direct (hops=0)
  name      id          hops snr    batt  last heard
  EXMP      !a1b2c3d4   ?    ?      87%   0s *self
  ALFA      !0a1b2c3d   0    -6.5   92%   40s <direct
  BRVO      !1122aabb   0    -14.0  ?%    5m  <direct
  CHRL      !99887766   2    -18.5  ?%    3h
------------------------------------------------------------------
MESSAGES received in window: 1
  [14:02:11] ch0 !0a1b2c3d: net check, anyone around?
DIRECT-RF neighbors heard in window: 2
PACKET activity by type: {'NODEINFO_APP': 3, 'TELEMETRY_APP': 5, 'TEXT_MESSAGE_APP': 1}
==================================================================
```

**How to read it:** `hops=0` + a real `snr` = a direct radio neighbor. `snr = None` = relayed/multi-hop. LONG_FAST decodes down to roughly **−20 dB SNR**, so a −18 dB link is real but faint (expect it to drop in and out). Meshtastic keeps **no host-side message history** — only messages that arrive during the listen window appear.

---

## LAN access (no Bluetooth)

nRF52 boards have **no WiFi**, so they can't host the web UI or join your LAN themselves. This bridges the USB link instead:

```
node ─USB─► serial-tcp-bridge :4403 ─┬─► phone/desktop app  (New connection → IP → <LAN_IP>:4403)
                                      └─► http-proxy :8080 ─► web client :3000  (auto-connects)
```

```bash
cd lan
./setup.sh              # one-time: fetches the http-proxy + prebuilt web client
./start-lan-stack.sh    # prints your LAN IP + the URLs
```

- **Phone/desktop app:** *New connection → IP/TCP →* `<LAN_IP>:4403`. Full map/messaging/config, no BLE.
- **Browser:** open `http://<LAN_IP>:3000` — it auto-connects to the proxy. (Override `?proxy=host:port`, disable with `?noauto`.)
- **Lightweight alternative:** `python scripts/lan-dashboard.py` serves a minimal USB-backed status page on `:8765` with no proxy/web-client needed.

The bridge (`scripts/serial-tcp-bridge.py`) **multiplexes** (app + web + tools at once), writes frames atomically so clients can't corrupt each other, serializes each client's config handshake, and **auto-reopens the serial port** when the node is unplugged or moved (USB re-enumerates). Details: [`lan/README.md`](lan/README.md).

> Third-party pieces (`meshtastic/web`, `meshtastic-http-proxy`) are **fetched by `setup.sh`, not vendored** — they stay with their upstream projects and licenses.

---

## Scripts

| Script | Purpose |
|---|---|
| `scripts/detect.sh` | List serial ports + USB tree; flag a charge-only cable |
| `scripts/diagnose.py` | Connect (hard timeout) → firmware / region / preset / channels / nodes |
| `scripts/assert-config.py` | PASS/FAIL checks (region≠UNSET, preset, tx, primary channel) — read-only |
| `scripts/report.py` | Full status report: device, channels, node table, live messages, packets |
| `scripts/monitor.py` | Live packet stream + node-table growth (`--seconds N`) |
| `scripts/flash-stable.sh` | Download + MD5-verify + serial-DFU flash of the latest stable firmware |
| `scripts/import-channel.sh` | Import a community channel from an official share URL |
| `scripts/serial-tcp-bridge.py` | Own the USB port; re-serve as Meshtastic TCP (:4403), multi-client + auto-reconnect |
| `scripts/lan-dashboard.py` | Minimal USB-backed web status dashboard (:8765) |

Every script is macOS-friendly (no GNU-only flags), and the Python ones fail safe with hard timeouts instead of hanging.

---

## Safety notes

- **Never invent a channel PSK or share URL** — join a community channel only with its *official* key/URL.
- **Flashing rewrites firmware.** The flasher pulls a **stable** release and MD5-verifies before writing, but confirm you want to reflash first.
- Region/regulatory settings (frequency, duty cycle, TX power) are your responsibility for your locale.

## Contributing

Issues and PRs welcome — especially: other nRF52/ESP32 boards, Linux/Windows parity for the shell scripts, and hardening the bridge's multi-client handling. See [`AGENTS.md`](AGENTS.md) if you're an AI agent working in this repo.

## License

[MIT](LICENSE).

Not affiliated with the Meshtastic project. "Meshtastic" is a trademark of its owners; this is an independent community tool.
