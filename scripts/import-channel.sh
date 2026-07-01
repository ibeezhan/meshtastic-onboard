#!/usr/bin/env bash
# L3 — Import a community channel (and its exact name+PSK) from an official
# Meshtastic channel-share URL. This is the ONLY correct way to join a community
# mesh like Lisboa-e-Arredores: the URL carries the exact AES key. Never invent a
# PSK by hand.
#
# A share URL looks like:  https://meshtastic.org/e/#CgMSAQ...
# Get the real one from the community (Discord / site / a member's QR) -- a
# Google search for the community name usually finds it.
#
# IMPORTANT: `--seturl` REPLACES the channel set. Meshtastic share URLs normally
# include the full set (LongFast primary + the community secondary), so the
# primary is preserved -- but always eyeball the URL's channel list first, and
# re-run diagnose.py afterward to confirm LongFast is still PRIMARY.
#
# Usage: bash import-channel.sh "<share-url>" [/dev/cu.usbmodemXXXX]
set -euo pipefail

URL="${1:-}"
PORT="${2:-$(ls /dev/cu.usbmodem* 2>/dev/null | head -1 || true)}"

[ -n "$URL" ] || { echo "usage: bash import-channel.sh \"<share-url>\" [port]"; exit 2; }
[ -n "$PORT" ] || { echo "FAIL: no serial port. Run detect.sh (L0)."; exit 2; }

case "$URL" in
  https://meshtastic.org/e/#*|https://*/e/#*) : ;;
  *) echo "WARN: '$URL' doesn't look like a .../e/# share URL. Continuing anyway." ;;
esac

MESHTASTIC="$(command -v meshtastic || echo "$HOME/.local/bin/meshtastic")"
[ -x "$MESHTASTIC" ] || { echo "FAIL: meshtastic CLI not found. Run: pipx install meshtastic"; exit 2; }

echo "About to import channel set onto $PORT from:"
echo "    $URL"
echo "(This applies the URL's channels. Primary LongFast is preserved if the URL"
echo " includes it -- verify with diagnose.py afterward.)"
echo
echo "+ $MESHTASTIC --port $PORT --seturl \"$URL\""
"$MESHTASTIC" --port "$PORT" --seturl "$URL"

echo
echo "DONE. Verify with: python diagnose.py $PORT"
