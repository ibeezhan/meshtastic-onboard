# meshtastic-onboard

[![ci](https://github.com/ibeezhan/meshtastic-onboard/actions/workflows/ci.yml/badge.svg)](https://github.com/ibeezhan/meshtastic-onboard/actions/workflows/ci.yml)
&nbsp;[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Put your AI agent — and you — on an off-grid mesh. Message other people and their agents over LoRa radio, with no internet, SIM, or infrastructure.**

A [Claude Code](https://docs.anthropic.com/en/docs/claude-code) **skill** (plus standalone scripts) that lets an AI agent get a [Meshtastic](https://meshtastic.org) node running and *communicate over it*: send and receive encrypted text across a self-healing LoRa mesh, see who's around, and hand the user an easy dashboard.

Meshtastic nodes are cheap ($25–40) LoRa radios that relay messages hop-to-hop for kilometers. Give one to your agent and it gains a **communication channel that works when the internet doesn't** — disaster response, remote areas, festivals, sailing, or just resilient peer-to-peer messaging between people who each have an agent on the mesh.

---

## Why an agent on the mesh?

- 🛰️ **Infrastructure-free comms.** No cell tower, no Wi-Fi, no account. Two radios in range talk directly; more radios extend the range for everyone.
- 🤝 **Agent-to-agent, and agent-to-people.** Your agent can broadcast to everyone on the public channel or DM a specific node — reaching other users' agents and humans alike.
- 🔒 **Encrypted by channel.** Each channel is an AES key; the public `LongFast` channel is shared globally, private channels reach only those you share a key with.
- 🖥️ **Easy for the human.** One command puts the node on your LAN — open a browser dashboard or the full map/messaging web client, no Bluetooth pairing dance.

---

## Quickstart

```bash
pipx install meshtastic                 # Meshtastic Python lib
git clone https://github.com/ibeezhan/meshtastic-onboard ~/.claude/skills/meshtastic-onboard
```

Then just ask your agent:

> *"Get my Meshtastic node online and send 'hello mesh' to the public channel."*
> *"Listen for messages on the mesh and summarize them."*
> *"Put my node on the LAN so I can open the dashboard."*

Or drive the scripts directly:

```bash
python scripts/report.py                       # who's on the mesh + recent messages + signal
python scripts/mesh-message.py send "hello mesh"          # broadcast to the public channel
python scripts/mesh-message.py send "hi" --to !a1b2c3d4   # direct-message one node
python scripts/mesh-message.py listen                     # stream incoming messages as JSON
cd lan && ./setup.sh && ./start-lan-stack.sh   # phone app + browser web client on your LAN
```

---

## Capabilities

### 1. Connect
Plug a Meshtastic node in over USB. `scripts/detect.sh` and `scripts/diagnose.py` confirm it's alive and read its config (region, channels, node list). If a fresh board needs firmware, `scripts/flash-stable.sh` installs the latest stable release.

### 2. Message — the core
```bash
python scripts/mesh-message.py send "text" [--ch N] [--to !nodeid] [--ack]
python scripts/mesh-message.py listen [--seconds N]
```
JSON in, JSON out — built for an agent to drive. Broadcast to everyone on a channel, or DM a node. `listen` emits one JSON object per incoming message (`from`, `channel`, `text`, `snr`, `hops_away`) so your agent can read the mesh and respond. This is how two people, each running an agent, cross-communicate over the air.

**Ready-to-run demo:** [`examples/agent-chat-loop.py`](examples/agent-chat-loop.py) is the full listen→decide→reply loop in ~40 lines (answers `ping` with `pong` out of the box). Swap its `respond()` for your own logic — call an LLM, run a command — and you have an agent living on the mesh.

### 3. See the mesh
```bash
python scripts/report.py         # node table (who you hear + signal), live messages, channel activity
python scripts/monitor.py        # live packet stream + node list as it grows
```

### 4. Dashboard & LAN access (no Bluetooth)
nRF52 nodes have no Wi-Fi, so this bridges the USB link onto your LAN:
```bash
cd lan && ./setup.sh && ./start-lan-stack.sh
```
- **Phone/desktop app:** connect via IP → `<LAN_IP>:4403` (full map/messaging/config).
- **Browser:** open `http://<LAN_IP>:3000` — the real Meshtastic web client, auto-connects.
- **Minimal dashboard:** `python scripts/lan-dashboard.py` → a status page on `:8765`.

The bridge multiplexes, so your agent's tools and the human's dashboard can use the one USB node at the same time.

---

## Scripts

| Script | What it does |
|---|---|
| `scripts/mesh-message.py` | **Send & receive text over the mesh (JSON I/O) — agent comms** |
| `scripts/report.py` | Full status: node table, live messages, signal, channel activity |
| `scripts/monitor.py` | Live packet stream + node-list growth |
| `scripts/diagnose.py` | Read firmware / region / channels / nodes |
| `scripts/detect.sh` | Is a node on the USB bus? |
| `scripts/assert-config.py` | PASS/FAIL config sanity checks (read-only) |
| `scripts/import-channel.sh` | Join a community channel from an official share URL |
| `scripts/flash-stable.sh` | Install the latest stable firmware (recovery) |
| `scripts/serial-tcp-bridge.py` | Re-serve the USB node as Meshtastic TCP (:4403); multi-client + auto-reconnect |
| `scripts/lan-dashboard.py` | Minimal USB-backed web dashboard (:8765) |

See [`SKILL.md`](SKILL.md) for the agent runbook and [`AGENTS.md`](AGENTS.md) for the machine-readable tool contracts. Sample outputs are in [`examples/`](examples).

---

## Hardware

Works with any [Meshtastic-supported node](https://meshtastic.org/docs/hardware/devices/). Developed and tested on the **Seeed SenseCAP T1000-E** (nRF52840). The scripts are macOS-first (`ioreg`/`lsof`); Linux/Windows parity is a welcome contribution.

**Node won't connect?** Quick checks, in order: use a **data** USB cable (charge-only cables are the #1 culprit), make sure the node is awake, and if a fresh/dev firmware won't respond, flash stable (`scripts/flash-stable.sh`). The full checklist is in `SKILL.md`.

---

## Safety & conduct

- **Never fabricate a channel key or share URL** — join a community channel only with its official key.
- Anything you send **transmits publicly over the air** to everyone on that channel — mind the airtime (Meshtastic is low-bandwidth) and be a good neighbor.
- Region/regulatory settings (frequency, duty cycle, TX power) are your responsibility for your locale.

## License

[MIT](LICENSE). Not affiliated with the Meshtastic project; "Meshtastic" is a trademark of its owners. This is an independent community tool.
