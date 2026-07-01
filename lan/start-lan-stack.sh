#!/usr/bin/env bash
# Start the LAN access stack for a USB-connected (non-WiFi) Meshtastic node.
#
#   node --USB--> [serial-tcp-bridge :4403] --TCP--> {  phone/desktop app (direct)      }
#                                                    {  http-proxy :8080 --> web :3000    }
#
# Result:
#   * Phone/desktop Meshtastic APP:  connect via IP  <LAN_IP>:4403          (path B)
#   * Browser web client:            open  http://<LAN_IP>:3000            (path A)
#
# Run ./setup.sh once first (fetches the http-proxy + web client). Then:
#   ./start-lan-stack.sh [SERIAL_DEV]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS="$HERE/../scripts"
DEV="${1:-$(ls /dev/cu.usbmodem* 2>/dev/null | head -1)}"
MESH_PY="${MESH_PY:-$HOME/.local/pipx/venvs/meshtastic/bin/python}"
PROXY_DIR="$HERE/http-proxy"
WEB_DIR="$HERE/web-client"
LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo '<lan-ip>')"

log(){ printf '\033[36m[stack]\033[0m %s\n' "$*"; }
free_port(){ local p; for p in "$@"; do lsof -tiTCP:"$p" -sTCP:LISTEN 2>/dev/null | xargs -r kill -9 2>/dev/null || true; done; }

[ -n "$DEV" ] || { echo "No /dev/cu.usbmodem* found. Plug in the node."; exit 1; }
[ -d "$PROXY_DIR" ] && [ -d "$WEB_DIR" ] || { echo "Missing http-proxy/ or web-client/. Run ./setup.sh first."; exit 1; }
[ -x "$MESH_PY" ] || MESH_PY="$(command -v python3)"

log "serial device: $DEV"
free_port 4403 8080 3000
lsof -t "$DEV" 2>/dev/null | xargs -r kill -9 2>/dev/null || true
sleep 1

log "1/3 serial->TCP bridge on :4403"
nohup "$MESH_PY" "$SCRIPTS/serial-tcp-bridge.py" "$DEV" 4403 >"$HERE/bridge.log" 2>&1 & disown
sleep 2

log "2/3 http-proxy on :8080 (-> bridge 127.0.0.1:4403)"
if [ ! -x "$PROXY_DIR/.venv/bin/uvicorn" ]; then
  log "  bootstrapping proxy venv (first run)"
  PY312="$(command -v python3.12 || command -v python3)"
  "$PY312" -m venv "$PROXY_DIR/.venv"
  "$PROXY_DIR/.venv/bin/pip" install -q --disable-pip-version-check -r "$PROXY_DIR/requirements.txt"
fi
( cd "$PROXY_DIR" && MESHTASTIC_TCP_HOST=127.0.0.1 \
  nohup "$PROXY_DIR/.venv/bin/uvicorn" main:app --host 0.0.0.0 --port 8080 >"$HERE/proxy.log" 2>&1 & disown )
sleep 3

log "3/3 web client on :3000"
( cd "$WEB_DIR" && nohup python3 -m http.server 3000 --bind 0.0.0.0 >"$HERE/web.log" 2>&1 & disown )
sleep 1

cat <<EOF

========================================================================
 LAN stack up.  LAN IP: $LAN_IP
------------------------------------------------------------------------
 PHONE APP (simplest):  New connection -> IP -> $LAN_IP  port 4403
 WEB CLIENT (browser):  open  http://$LAN_IP:3000   (auto-connects)
------------------------------------------------------------------------
 logs: bridge.log  proxy.log  web.log   |   stop: ./stop-lan-stack.sh
========================================================================
EOF
