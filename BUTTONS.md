# Contextual buttons — status & enablement

The LCD + LED app-switching is **done and working**. Contextual buttons are **wired in
software and compiled**, but need 3 device-side steps (deferred so they don't risk the
working setup before office use).

## What's ready
- **`modes.bin`** (975 B) — compiled from `gen_modes.py` → `modes.v3`. A mode-branching
  button script: it reads the mode from zone-1's LED color (`SELECTED_LED_COL & 255`)
  and dispatches per-app keystrokes. Recompile after edits:
  `./venv/bin/python -c "import sys;sys.path.insert(0,'.');from sayo_toolkit.assembler import assemble;open('modes.bin','wb').write(assemble(open('modes.v3').read()))"`
- **Daemon mode-signaling** — behind `button_script_enabled` in `sayo_config.json`
  (currently `false`). When `true`, the daemon puts the mode ID in zone-1's red channel
  (middle button goes dark) and the icon color on the side buttons.

## Per-app button map (edit in `gen_modes.py`, then recompile)
Button order V0: 0=Left 1=Middle 2=Right 3=knob-press 4=knob-CCW 5=knob-CW.
- **mode 1 (vim)**: Left `<ESC>qq` (record) · Middle `<ESC>@q` (play) · Right `<ESC>:w`
  (save) · knob `<ESC>q` (stop rec) · CCW `:bp` · CW `:bn`
- **mode 2 (browser)**: back / new-tab / forward / reload / prev-tab / next-tab
- **mode 3 (youtube)**: j / k / l / f / vol-down / vol-up
- **mode 4 (intellij)**: step-into / step-over / resume / breakpoint / stop / step-out
- **mode 0 (default)**: media prev/play/next/mute/vol

## STATUS: WORKING (2026-07-13)
- ✅ Script flashed (slot 0 "modes"), all 6 buttons bound to it, mode-signaling ON.
- ✅ vim macros CONFIRMED: Left=record / Middle=play / Right=save. Knob 3/4/5 bound.
- Binding format cracked: LIVE write `_wrap([3C 00][10][key][56B])`, keymode `0x40`=
  scripts, **arg0 at data offset 20 -> V0** (device does NOT auto-set V0; bind arg0=key#).
  Save via report-0x02 build_packet(4,[0x72,0x96]). See memory app-aware-daemon-shipped.

## Finish path A — web app (reliable, ~2 min) — RECOMMENDED before office use
1. Stop the daemon so the web app can grab the device:
   `launchctl unload ~/Library/LaunchAgents/com.shauny.sayodaemon.plist`
2. `sayodevice.com` → connect. For **each of the 6 buttons**, set its action to
   **run script → slot 0 (modes)**. The device auto-sets `V0` = the key index, which the
   script branches on. Then run **Calibrate** (hands off the keys) to stop the `x`-typing.
3. Set `"button_script_enabled": true` in `sayo_config.json`, then reload the daemon:
   `launchctl load ~/Library/LaunchAgents/com.shauny.sayodaemon.plist`

## Finish path B — capture-assisted automation (for a future session)
The one missing piece is the **"run script" binding byte format** — the backups only have
key-*type* bindings (HID codes i/k/l), never a script-run action, and the web app config
doesn't expose the encoding. To automate binding all 6 buttons + writing calibration:
1. Arm the WebHID capture (see `capture12.js` pattern), connect the web app.
2. Bind **ONE** button to "run script slot 0" in the web app → capture the exact bytes.
3. That reveals the run-script action encoding; then write all 6 bindings + the
   calibration (region `0x1c`, data in `analogkeyv2.sayobak`) via the chunk protocol.

## Reverse-engineering state (facts gathered this session)
- **Keybindings**: 60-byte records `[0x10][key_idx][0x38 0x00][56 data]`. Data =
  `[00 00][enable 01][keycfg][00 00]` + analog thresholds (5×2-byte LE, e.g. `e8 03`=1000
  actuation, `b8 0b`=3000 top, `08 07`=1800) + multiple (type,value) action slots. Old
  backup actions are HID keycodes (`0c`=i,`0e`=k,`0f`=l) — NOT script-run.
- **Calibration**: region `0x1c`, read via `04 00 1c <n>`; `analogkeyv2.sayobak` = 3
  records of 30 bytes (`1c 00 18 00 ...` + 24 bytes per-key sensor min/max ADC). Writing
  it can restore calibration but is sensor-specific — verify or prefer web-app Calibrate.
- Config regions use the **image chunk protocol** with different region IDs
  (`1a00`=script, `2000`=image, `1c..`=calib) bracketed by `08 00 <region> ffffffff`.
