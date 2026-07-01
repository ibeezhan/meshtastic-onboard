#!/usr/bin/env bash
# Stop the LAN access stack (bridge :4403, proxy :8080, web :3000) and free the serial port.
set -uo pipefail
for p in 4403 8080 3000; do lsof -tiTCP:"$p" -sTCP:LISTEN 2>/dev/null | xargs -r kill -9 2>/dev/null || true; done
for d in /dev/cu.usbmodem*; do lsof -t "$d" 2>/dev/null | xargs -r kill -9 2>/dev/null || true; done
echo "LAN stack stopped; serial port freed."
