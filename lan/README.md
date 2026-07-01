# LAN access for a USB (non-WiFi) Meshtastic node

nRF52 boards (e.g. the SenseCAP T1000-E) have **no WiFi**, so they can't join your
LAN or host the Meshtastic web UI themselves. Their only native links are **USB
serial** and **BLE** — and BLE is flaky. This stack turns the USB connection into
stable LAN access, with no Bluetooth involved.

## Architecture

```
 node ──USB serial──► serial-tcp-bridge  :4403 ─┬─► phone/desktop APP  (direct TCP)
                      (owns the USB port,        │
                       fans out to N clients)    └─► http-proxy :8080 ──► web-client :3000
```

- **bridge** (`../scripts/serial-tcp-bridge.py`) — owns the USB port and re-serves
  it as the standard Meshtastic **TCP API on :4403** (serial and TCP share identical
  framing). Multiplexes (app + web + tools at once), writes client frames
  atomically, serializes each client's config handshake, and **auto-reopens** the
  serial port when the node is unplugged/moved.
- **http-proxy** (`http-proxy/`, from
  [ianmcorvidae/meshtastic-http-proxy](https://github.com/ianmcorvidae/meshtastic-http-proxy))
  — connects to the bridge over TCP and exposes the ESP32-style **HTTP API on :8080**
  (`/api/v1/fromradio`, `/api/v1/toradio`), which the browser web client speaks.
- **web-client** (`web-client/`, a prebuilt [meshtastic/web](https://github.com/meshtastic/web)
  release) — the real client (map, messaging, config) served as static files on
  **:3000**, with a small `autoconnect.js` injected for one-click connect.

> `http-proxy/` and `web-client/` are **fetched by `setup.sh`, not committed** — they
> belong to their upstream projects.

## Run

```bash
./setup.sh              # one-time: clone http-proxy, download web client, inject autoconnect
./start-lan-stack.sh    # start all three; prints your LAN IP + URLs
./stop-lan-stack.sh     # stop them and free the USB port
```

Only one process can own the USB serial port at a time — start this stack **or** a
direct `diagnose.py` / the web-serial client, not both.

## Connect

**Phone/desktop app (simplest, rock-solid):**
Meshtastic app → *New connection* → **IP/TCP** → host = your LAN IP, port **4403**.

**Browser web client:**
1. Open `http://<LAN_IP>:3000` on any device on the WiFi.
2. It **auto-connects** to the proxy (`<LAN_IP>:8080`) via `autoconnect.js`.
3. Manual fallback: `http://<LAN_IP>:3000/?noauto` → *New connection* → **HTTP** tab
   → type `<LAN_IP>:8080` → **Connect**. (No TLS toggle in current builds — the
   scheme is inferred from what you type; `host:port` ⇒ `http://…`.)

Override the proxy with `?proxy=host:port`; disable auto-connect with `?noauto`.

## Lightweight alternative

If you don't want the proxy + web-client build, `python ../scripts/lan-dashboard.py`
serves a minimal USB-backed status page (nodes, config, live counts) on `:8765`.
