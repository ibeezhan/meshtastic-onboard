# AGENTS.md — guidance for AI agents

This repo is a Meshtastic node onboarding/debug toolkit. If you're an autonomous
agent (Claude Code or similar) helping a user with a Meshtastic node, read this
before acting. `SKILL.md` is the human-facing runbook; this file is the machine
contract.

## Golden rules

1. **Diagnose bottom-up. Do not skip layers.** A symptom at L4 ("no nodes") is
   usually caused at L0–L2. Always confirm the USB link and device liveness before
   touching config or firmware.
2. **Liveness = the API answers. Nothing else.** On the T1000-E the USB product
   string reads `..._BOOT` even when the application firmware is running. **Never**
   conclude "stuck in bootloader" from that string, mounted drives, or LEDs. The
   only proof of life is a successful `diagnose.py` / API connect.
3. **Never fabricate secrets.** Do not invent a channel PSK, a `meshtastic.org/e/#`
   share URL, a region, or a frequency. If the user wants a community channel, get
   the *official* URL/key from them or a cited public source.
4. **Confirm before irreversible or outward actions.** Flashing firmware, factory
   resets, and anything that publishes/transmits should be confirmed with the user
   first. Report failures honestly (show the actual error/output).
5. **Only one process may own the USB serial port.** The bridge, a direct
   `diagnose.py`, and the browser web-serial client are mutually exclusive. Prefer
   running the **bridge** as the single owner and pointing everything else at TCP.

## Decision tree

```
detect.sh → no /dev/cu.usbmodem*?
    → suspect CHARGE-ONLY CABLE (most common) or asleep node. Ask user to swap
      cable / press the button. STOP until a port appears.
port exists → diagnose.py
    → API answers? 
        yes → check region:
                UNSET → set region (e.g. EU_868). This alone causes "no nodes".
                set   → check preset (LONG_FAST default), tx_enabled, channels.
        no (times out) → serial API is silent → almost always a bad dev/nightly
              firmware. Recommend flashing STABLE (flash-stable.sh). Confirm first.
config OK but node list empty → this is NORMAL right after a flash/reset.
    → run monitor.py; nodeDB refills over minutes–hours. Distinguish direct-RF
      (non-null SNR) from relayed (null SNR). If still nothing after a sustained
      run → L5 RF: antenna, indoors, out of range (placement, not config).
```

## Script contracts

All Python scripts prefer `~/.local/pipx/venvs/meshtastic/bin/python` (has the
`meshtastic` lib + `pyserial`) and use hard timeouts so they never hang forever.
`TARGET` for connect-capable scripts is `tcp` / `tcp:HOST` (via the bridge) or a
`/dev/cu.usbmodem*` path / `serial`.

| Script | Args | Reads | Writes / side effects | Output to parse |
|---|---|---|---|---|
| `detect.sh` | — | USB tree | none | port list; "charge-only?" hint |
| `diagnose.py` | `[TARGET]` | device | none | fw, region, preset, tx, hop, channels, node count |
| `assert-config.py` | `[TARGET]` | device | none | `PASS`/`FAIL` lines per check |
| `report.py` | `[TARGET] [LISTEN_SECS]` | device + live packets | none | full report incl. node table, messages, packet counts |
| `monitor.py` | `[TARGET] [--seconds N]` | device + live packets | none | streamed packets + periodic node table |
| `import-channel.sh` | `<share-url>` | — | **mutates channel set** on device | confirmation |
| `flash-stable.sh` | — | network + device | **rewrites firmware** (MD5-verified) | progress + "Device programmed" |
| `serial-tcp-bridge.py` | `[DEV] [PORT]` | owns USB | serves TCP :4403 | log lines |
| `lan-dashboard.py` | `[DEV] [HTTP_PORT]` | owns USB | serves HTTP :8765 | log lines + JSON at `/api/info` |

Scripts that **mutate** (`import-channel.sh`, `flash-stable.sh`) are the ones to
gate behind explicit user confirmation. The rest are read-only/observational.

## Environment assumptions & known traps

- Built for **macOS** (`ioreg`, `lsof`, `ipconfig getifaddr`, `md5`, no GNU-only
  flags, no `timeout`). Linux/Windows parity is a good contribution.
- **T1000-E flashing** uses serial DFU: `adafruit-nrfutil dfu serial -pkg <ota.zip>
  -p <port> -b 115200 -t 1200`. The `-t 1200` (1200-baud touch) is **required** to
  wake the bootloader's DFU listener — without it you get `No data received`.
- **macOS UF2 drag-drop trap:** `cp file.uf2 /Volumes/<BOOT>/` fails with
  `could not copy extended attributes: Device not configured` and *truncates* the
  write. Use `cat file.uf2 > /Volumes/<BOOT>/fw.uf2` instead.
- **Moving the node re-enumerates USB** → a long-running bridge/dashboard holding a
  stale handle sees `Errno 6: Device not configured`. The bridge auto-reconnects;
  ad-hoc scripts should be restarted.
- **nRF52 has no WiFi** → the node can't host the web UI or join the LAN; the
  browser web client needs the bridge + http-proxy (see `lan/`).

## When you're stuck

If two or three tool attempts fail the same way, stop and report to the user what
you tried, the exact error, and your best hypothesis — don't loop. Hardware +
radio problems often need a physical action only the user can take (swap cable,
press button, move the node, accept a firmware flash).
