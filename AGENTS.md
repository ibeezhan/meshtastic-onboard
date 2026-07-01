# AGENTS.md — machine contract for AI agents

You are an AI agent using this toolkit to put a user on the [Meshtastic](https://meshtastic.org)
LoRa mesh and communicate over it. `SKILL.md` is the human-facing runbook; this is
the tool contract. `README.md` is the pitch.

## What you can do

1. **Connect** a Meshtastic node over USB and read its state.
2. **Message** — send and receive encrypted text over the air (agent-to-agent, or to
   other people and their agents). This is the primary use case.
3. **Observe** the mesh — who's reachable, signal quality, live activity.
4. **Expose** the node on the LAN so the human gets a dashboard / web client.

## Core loop: communicate

```
# broadcast to everyone on the public channel
python scripts/mesh-message.py send "text"
# direct message a node
python scripts/mesh-message.py send "text" --to !<nodeid>
# read the mesh: one JSON object per incoming message
python scripts/mesh-message.py listen --seconds N
```
`listen` emits JSON lines: `{ts, from, from_self, channel, snr, hops_away, text}`.
To hold a conversation, run `listen` (or parse `report.py`) to read, then `send` to
reply. Ignore `from_self:true`. Reach = whoever shares the channel's key; `LongFast`
(default key `AQ==`) is the global public channel.

## Tool contracts

All connect-capable scripts take `TARGET` = `tcp` / `tcp:HOST` (via the bridge) or a
`/dev/cu.usbmodem*` path / `serial`. Python scripts prefer
`~/.local/pipx/venvs/meshtastic/bin/python` and use hard timeouts.

| Script | Args | Side effects | Output |
|---|---|---|---|
| `mesh-message.py send` | `"text" [--ch N] [--to !id] [--ack] [--target T]` | **transmits over the air** | JSON `{ok, sent, channel, to, wantAck}` |
| `mesh-message.py listen` | `[--seconds N] [--target T]` | none | JSON line per received text message |
| `report.py` | `[TARGET] [LISTEN_SECS]` | none | node table, messages, signal, packet counts |
| `monitor.py` | `[TARGET] [--seconds N]` | none | streamed packets + periodic node table |
| `diagnose.py` | `[TARGET]` | none | fw, region, preset, tx, channels, node count |
| `assert-config.py` | `[TARGET]` | none | `PASS`/`FAIL` per check |
| `detect.sh` | — | none | serial ports + USB tree |
| `import-channel.sh` | `<share-url>` | **mutates channel set** | confirmation |
| `flash-stable.sh` | — | **rewrites firmware** (MD5-verified) | progress |
| `serial-tcp-bridge.py` | `[DEV] [PORT]` | owns USB; serves TCP :4403 | log lines |
| `lan-dashboard.py` | `[DEV] [HTTP_PORT]` | owns USB; serves HTTP :8765 | log + JSON at `/api/info` |

**Gate behind explicit user confirmation:** `send` (public transmission),
`import-channel.sh`, `flash-stable.sh`. Everything else is read-only/observational.

## Rules

1. **Sending transmits publicly.** A `send` goes over the air to every node on that
   channel — real people. Confirm intent, keep messages short, don't flood (LoRa is
   low-bandwidth and duty-cycle-limited).
2. **Never fabricate secrets** — no invented channel PSK, share URL, region, or
   frequency. Get community channels from their official URL.
3. **One process owns the USB port.** Run `serial-tcp-bridge.py` as the single owner
   and point messaging/observability tools at `tcp:` so they share the node with the
   dashboard. Don't open the raw serial port while the bridge holds it.
4. **Confirm firmware flashes and config mutations** before running them, and report
   failures with the actual error.

## If connect fails

Don't loop. Check, in order: is there a `/dev/cu.usbmodem*` (else likely a
**charge-only cable** — ask the user to swap it or wake the node)? Does `diagnose.py`
answer (if it times out on a fresh board, recommend `flash-stable.sh`)? Is `region`
set (not `UNSET`)? An empty node list right after a flash is **normal** — it refills
over minutes to hours. Persistent silence with good config is an **RF/placement**
problem (antenna, indoors, range), which only the user can fix physically. After two
or three failed attempts, stop and report what you tried, the exact error, and your
best hypothesis.
