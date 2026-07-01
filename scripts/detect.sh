#!/usr/bin/env bash
# L0 — Is a Meshtastic node physically on the USB bus?
# Lists serial ports and the USB device tree, and flags the charge-only-cable case.
# macOS-friendly: no GNU-only flags, no `timeout`.
set -u

echo "=== L0: USB enumeration check ==="
echo

echo "--- serial ports (/dev/cu.usbmodem*) ---"
PORTS=$(ls /dev/cu.usbmodem* 2>/dev/null)
if [ -n "$PORTS" ]; then
  echo "$PORTS"
else
  echo "(none)"
fi
echo

echo "--- USB tree: Seeed / Nordic / T1000 devices ---"
USBHITS=$(ioreg -p IOUSB -l 2>/dev/null \
  | grep -i "USB Product Name" \
  | grep -iE "t1000|seeed|nordic|nrf|tracker")
if [ -n "$USBHITS" ]; then
  echo "$USBHITS" | sed 's/^[[:space:]]*//'
else
  echo "(no Seeed/Nordic/T1000 device found in USB tree)"
fi
echo

echo "=== verdict ==="
if [ -n "$PORTS" ]; then
  echo "OK: a serial port exists -> proceed to L1 (python diagnose.py)."
  echo "Note: the T1000-E may still show its USB name as 'T1000_E_BOOT' even when"
  echo "      the app is running. Do NOT assume bootloader -- L1 is the only truth."
elif [ -n "$USBHITS" ]; then
  echo "PARTIAL: device seen on USB but no serial port yet -- give it a few seconds,"
  echo "         or wake the node with its button (the T1000-E sleeps aggressively)."
else
  echo "FAIL: nothing on the bus. Most likely a CHARGE-ONLY USB cable (the #1 gotcha)."
  echo "      Swap to a known-good DATA cable. Second guess: device asleep -> press button."
fi
