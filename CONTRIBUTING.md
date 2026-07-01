# Contributing

Thanks for helping make Meshtastic easier for AI agents and their humans. Issues and
PRs are welcome — especially more boards, Linux/Windows parity, and richer messaging.

## Dev setup

```bash
pipx install meshtastic          # runtime lib the scripts use
pipx install adafruit-nrfutil    # only for flashing nRF52 boards
git clone https://github.com/ibeezhan/meshtastic-onboard
```

You don't need hardware to work on docs or to pass CI — only to run the scripts
against a real node.

## CI

Every push and PR runs [`.github/workflows/ci.yml`](.github/workflows/ci.yml), which
does two hardware-free checks:

- `bash -n` on every `*.sh` — shell syntax.
- `python -m py_compile` on every `*.py` — Python syntax.

That's the bar for a green check: **the code must parse.** It can't test radios in the
cloud, so keep runtime behaviour covered by clear code and the sample outputs in
[`examples/`](examples). Run the same checks locally before pushing:

```bash
for f in $(find . -name '*.sh'); do bash -n "$f"; done
python -m py_compile $(find . -name '*.py')
```

## Conventions

- **macOS-first, POSIX-friendly.** No GNU-only flags, no `timeout` (use a `read -t`
  loop or Python `signal.alarm`). Cross-platform improvements are very welcome.
- **Agent-friendly output.** Tools an agent drives (e.g. `mesh-message.py`) print
  **JSON**; human tools print readable tables. Keep scripts focused and under ~150 lines.
- **Fail safe.** Python scripts that connect use a hard timeout so they never hang.
- **Never hard-code secrets or personal data.** No real channel PSKs, share URLs, node
  IDs, IP addresses, or usernames. All examples use **fabricated** data.
- **Don't vendor third-party code.** The web client and http-proxy are fetched by
  `lan/setup.sh`, not committed.

## PR checklist

- [ ] `bash -n` + `py_compile` pass locally.
- [ ] New agent-facing tools output JSON; new human tools are readable.
- [ ] No secrets/personal data; any sample data is fabricated.
- [ ] Docs updated (`README.md` / `SKILL.md` / `AGENTS.md`) if behaviour changed.

## Scope

This repo is the **onboarding + communication + dashboard** layer for agents. Deep
firmware work belongs upstream in [meshtastic/firmware](https://github.com/meshtastic/firmware);
the web client in [meshtastic/web](https://github.com/meshtastic/web).
