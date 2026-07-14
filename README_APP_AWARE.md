# App-Aware SayoDevice O3C Macropad

Makes your "Shauny Buttons" O3C follow the **frontmost macOS app** — switching the
**LCD icon** and **button LED colors** automatically. Built entirely on reverse-engineered,
wear-free primitives (no flash writes during normal use).

## What works today

- **LCD**: shows a pre-loaded app icon, full-screen and clean, and it persists.
- **LEDs**: per-app button colors via the wear-free `cmd 16` channel.
- **Auto-switch**: a host daemon watches the foreground app and pushes both.

The daemon **only selects pre-loaded images** — it never uploads at runtime, which is
what keeps it reliable (uploads put the device into a "Loading"/transfer state).

## One-time setup

### 1. Load your icons (once, via the web app)
Open `sayodevice.com`, connect the device, and upload up to 7 images (slots 0–6).
Small icons centered on a **black background** look best and stay tiny in flash.
(You've already done this.)

### 2. Map slots → apps
Preview each slot and note which app it is:
```bash
./venv/bin/python sayo_show.py tour        # cycles slots 0..6, ~2.5s each
./venv/bin/python sayo_show.py 3            # show one slot
```
Then edit **`sayo_config.json`** so each rule's `slot` points at the right image.
Rules match the frontmost app's **name** (and an optional URL substring for browsers).
First match wins; `default` is the fallback. Colors are `[r,g,b]` for the LEDs.

### 3. Run the daemon
```bash
./venv/bin/python sayo_daemon.py            # follow the foreground app
./venv/bin/python sayo_daemon.py --once      # show what the current app maps to
./venv/bin/python sayo_daemon.py --verbose
```
Switch between apps and the icon + colors follow. To run it in the background
permanently, install the LaunchAgent (below).

## Buttons / calibration (important)

A factory reset (during recovery this session) cleared the key calibration and
bindings, so the **keys may auto-type `x`** until recalibrated. The reliable fix is
one web-app step:

1. `sayodevice.com` → connect → **Calibrate** (hands off the keys), **or** restore
   `sayo backups/analogkeyv2.sayobak` (calibration) + `keybinding.sayobak` (bindings)
   via the web app's import/restore.
2. Rename back to "Shauny Buttons" via the web app if you like
   (`sayo backups/devicename.sayobak`).

Calibration data is device/sensor-specific; writing it blind can wedge the device, so
this stays a web-app step by design. Everything else (LCD + colors) is fully automated.

## Files
- `sayo_daemon.py` — the app-follow loop (edit `sayo_config.json`).
- `sayo_config.json` — app → slot + color mapping.
- `sayo_show.py` — manual LCD/LED control for testing & slot-mapping.
- `sayo_dev.py` — device operations (select image, clear overlays, set colors).
- `sayo_lcd.py` — the LCD codec + upload protocol (the reverse-engineered core).
- `sayo backups/*.sayobak` — full device config backups (web-app restorable).
- `com.shauny.sayodaemon.plist` — LaunchAgent to auto-run the daemon.

## Recovery (if the screen/USB ever wedges)
Unplug, **hold the knob pressed** while replugging (~3s). This factory-resets and
restores USB enumeration; then reconnect the web app to reconfigure. See the toolkit
memory notes for the full protocol details.
