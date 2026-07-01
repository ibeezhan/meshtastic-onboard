---
name: meshtastic-onboard
description: Put an AI agent and its user on the Meshtastic LoRa mesh, then communicate over it. Use to get a Meshtastic node online, send and receive messages (agent-to-agent, or to other people and their agents), see who's on the mesh, join a community channel, or give the user an easy LAN dashboard / web client. Meshtastic is off-grid encrypted radio — no internet, SIM, or infrastructure. macOS-first; tested on the Seeed SenseCAP T1000-E (nRF52840).
---

# Meshtastic for AI agents

[Meshtastic](https://meshtastic.org) is an off-grid LoRa mesh: cheap radios that
relay encrypted text (plus telemetry/position) hop-to-hop for kilometers, with no
internet, SIM, or infrastructure. This skill lets **you, an AI agent**, get your
user's node online and *communicate over it* — send and receive messages, see who's
around, and hand the user an easy dashboard. Two people who each run an agent on the
mesh can cross-communicate entirely over the air.

Helper scripts are in `scripts/`. They prefer a Python with the `meshtastic` lib
(e.g. `~/.local/pipx/venvs/meshtastic/bin/python`) and fail safe with hard timeouts.
Install once:
```
pipx install meshtastic
```

Connect-capable scripts take a `TARGET`: `tcp` / `tcp:HOST` (through the bridge, so
they share the USB node with the dashboard), a `/dev/cu.usbmodem*` path, or `serial`.

---

## 1. Connect the node

```
bash scripts/detect.sh        # is a node on the USB bus?
python scripts/diagnose.py    # firmware, region, channels, node list
```
A node that answers `diagnose.py` is ready. Confirm **region is set** (e.g. `EU_868`,
`US`, …, never `UNSET`) and the primary channel is `LongFast` — that's the shared
public channel that makes you discoverable and reachable. If a fresh board's API is
silent, see *Troubleshooting* below.

## 2. Message — the core capability

```
python scripts/mesh-message.py send "hello mesh"              # broadcast to public channel
python scripts/mesh-message.py send "hi there" --to !a1b2c3d4 # direct-message one node
python scripts/mesh-message.py send "ack test" --ack          # request delivery ack
python scripts/mesh-message.py listen --seconds 120           # stream incoming as JSON
```
`send` transmits over the air to everyone on the channel (or to one node with `--to`).
`listen` prints one JSON object per incoming message — `from`, `channel`, `text`,
`snr`, `hops_away`, `from_self` — so you can read the mesh and respond in a loop. This
is the agent-to-agent / agent-to-people channel.

**Channels & reach:** a message goes only to nodes that share the channel's key.
- `LongFast` (default, key `AQ==`) = the **global public channel** — everyone in range.
- A private/community channel (32-byte key) = only those who imported it. Join one with
  its *official* share URL:
  ```
  bash scripts/import-channel.sh "https://meshtastic.org/e/#..."
  ```
  **Never invent a key or URL** — get the real one from the community.

**Airtime etiquette:** LoRa is low-bandwidth and duty-cycle-limited. Keep messages
short and don't flood the mesh; you're sharing the air with real people.

## 3. See who's on the mesh

```
python scripts/report.py      # node table (who you hear + signal), recent messages, activity
python scripts/monitor.py     # live packet stream; node list every 60s
```
In the node table, `hops=0` + a real `snr` = a **direct** radio neighbor; `snr=None`
= relayed/multi-hop. A freshly-flashed node starts with an empty list and fills in
over minutes to hours as nodes rebroadcast their info — that's normal.

## 4. Dashboard & LAN access (give the human easy access)

nRF52 nodes have no Wi-Fi, so bridge the USB link onto the LAN:
```
cd lan && ./setup.sh && ./start-lan-stack.sh
```
- **Phone/desktop app:** *New connection → IP/TCP →* `<LAN_IP>:4403` — full map/messaging/config, no Bluetooth.
- **Browser web client:** open `http://<LAN_IP>:3000` — auto-connects.
- **Minimal dashboard:** `python scripts/lan-dashboard.py` → status page on `:8765`.

The bridge (`scripts/serial-tcp-bridge.py`) multiplexes, so your messaging tools and
the human's dashboard use the one USB node simultaneously, and it auto-reopens the
port if the node is unplugged/moved.

---

## Troubleshooting (only if a step above fails)

Work top-down; each row is a distinct failure with a distinct fix.

| Symptom | Likely cause | Fix |
|---|---|---|
| No `/dev/cu.usbmodem*` at all | **Charge-only USB cable** (most common), or node asleep | Swap to a data cable; press the button to wake |
| Enumerates but `diagnose.py` times out | Bad/half-installed **dev-nightly firmware** | Flash stable: `bash scripts/flash-stable.sh` |
| Connects but sees no nodes | `region = UNSET` (radio won't TX/RX) | Set region (e.g. `EU_868`); re-check with `assert-config.py` |
| Node list empty right after a flash | Node DB was wiped — **this is normal** | Let `monitor.py` run; it refills over minutes–hours |
| Config fine, still hears nobody | RF: no antenna, deep indoors, out of range | Antenna on; move to a window/outdoors; check a community map |

Flashing detail (`flash-stable.sh`): it pulls the latest **stable** release, extracts
the board's OTA package, MD5-verifies, and flashes over serial DFU
(`adafruit-nrfutil dfu serial -pkg <ota.zip> -p <port> -b 115200 -t 1200`; the
`-t 1200` touch is required). Needs `pipx install adafruit-nrfutil`. After a flash,
re-confirm region + channels.
