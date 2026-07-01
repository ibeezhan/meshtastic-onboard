#!/usr/bin/env bash
# Recovery flash — download the latest STABLE Meshtastic firmware for the
# Seeed SenseCAP T1000-E and flash it over serial DFU (no UF2 drive, no
# double-tap gesture). Use this when L1 (diagnose.py) shows a silent serial API,
# the classic symptom of a bad/half-installed dev nightly.
#
# Each step is guarded and idempotent (re-running re-uses cached downloads).
# macOS-friendly: no GNU-only flags, no `timeout`.
#
# Usage: bash flash-stable.sh [/dev/cu.usbmodemXXXX]
set -euo pipefail

PORT="${1:-$(ls /dev/cu.usbmodem* 2>/dev/null | head -1 || true)}"
[ -n "$PORT" ] || { echo "FAIL: no serial port. Run detect.sh (L0)."; exit 2; }

NRFUTIL="$(command -v adafruit-nrfutil || echo "$HOME/.local/bin/adafruit-nrfutil")"
[ -x "$NRFUTIL" ] || { echo "FAIL: adafruit-nrfutil not found. Run: pipx install adafruit-nrfutil"; exit 2; }

WORK="${TMPDIR:-/tmp}/meshtastic-flash"
mkdir -p "$WORK/fw"
cd "$WORK"

echo "=== 1/5  resolve latest STABLE release ==="
API="https://api.github.com/repos/meshtastic/firmware/releases/latest"
NRFZIP_URL="$(curl -fsSL "$API" | grep -E '"browser_download_url".*firmware-nrf52840-' \
  | sed -E 's/.*"(https[^"]+)".*/\1/' | head -1)"
[ -n "$NRFZIP_URL" ] || { echo "FAIL: could not find firmware-nrf52840 asset."; exit 1; }
VER="$(echo "$NRFZIP_URL" | sed -E 's/.*firmware-nrf52840-(.*)\.zip/\1/')"
echo "    version: $VER"

echo "=== 2/5  download nrf52840 bundle (cached) ==="
ZIP="$WORK/nrf52840-$VER.zip"
[ -s "$ZIP" ] || curl -fsSL "$NRFZIP_URL" -o "$ZIP"
echo "    $(du -h "$ZIP" | cut -f1)  $ZIP"

echo "=== 3/5  extract tracker-t1000-e OTA + UF2 + erase + manifest ==="
unzip -o "$ZIP" '*tracker-t1000-e*' '*erase*' -d "$WORK/fw" >/dev/null
OTA="$(ls "$WORK"/fw/*tracker-t1000-e*-ota.zip | head -1)"
UF2="$(ls "$WORK"/fw/firmware-tracker-t1000-e-*.uf2 | head -1)"
MTJSON="$(ls "$WORK"/fw/*tracker-t1000-e*.mt.json | head -1)"
[ -s "$OTA" ] && [ -s "$UF2" ] || { echo "FAIL: extraction missing OTA/UF2."; exit 1; }
echo "    OTA: $(basename "$OTA")"

echo "=== 4/5  MD5-verify UF2 against bundled manifest ==="
if [ -s "$MTJSON" ]; then
  WANT="$(grep -A2 '\.uf2"' "$MTJSON" | grep -i md5 | head -1 | sed -E 's/.*"md5":[[:space:]]*"([0-9a-f]+)".*/\1/')"
  GOT="$(md5 -q "$UF2")"
  echo "    want=$WANT got=$GOT"
  [ -z "$WANT" ] || [ "$WANT" = "$GOT" ] || { echo "FAIL: MD5 mismatch -- not flashing."; exit 1; }
  echo "    integrity OK"
else
  echo "    (no manifest md5 to check against -- skipping)"
fi

echo "=== 5/5  flash via serial DFU ==="
echo "    NOTE: '-t 1200' touch is REQUIRED to wake the bootloader's DFU listener."
echo "    (Erase UF2 staged at $WORK/fw if a factory wipe is ever needed --"
echo "     drag with: cat <erase>.uf2 > /Volumes/T1000-E/erase.uf2, never cp.)"
"$NRFUTIL" dfu serial -pkg "$OTA" -p "$PORT" -b 115200 -t 1200

echo
echo "DONE. Re-run diagnose.py. Re-confirm region/channels (a flash can reset them):"
echo "  region EU_868, preset LONG_FAST, primary LongFast, then import the community URL."
echo "An empty NodeDB that refills over minutes->hours is NORMAL (see monitor.py)."
