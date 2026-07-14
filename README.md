# sayo-macropad

App-aware macropad daemon for the **SayoDevice O3C** on macOS. A background daemon watches
the frontmost app and switches the keyboard's **LCD icon**, **LED colors**, and **contextual
button functions** to match (vim macros in vim, browser nav in Safari/Chrome, etc.).

Built on a from-scratch reverse-engineering of the O3C's LCD image format, screen-layer
protocol, and on-device scripting VM.

## Plug-and-play install (macOS, needs `git`)

```bash
git clone https://github.com/batterts/sayo-macropad.git ~/sayo && cd ~/sayo && ./setup.sh
```

That creates a venv, installs deps, and loads a LaunchAgent so the daemon auto-starts and
follows your foreground app. The **device holds its own config** (icons, button bindings,
calibration) in flash — this repo is just the host-side driver.

## Usage
- `./venv/bin/python sayo_daemon.py --once` — show what the current app maps to
- `./venv/bin/python sayo_show.py tour` — preview the on-device icon slots
- edit `sayo_config.json` — map apps → icon slot + LED color + button mode

See **README_APP_AWARE.md** (full setup/usage/recovery) and **BUTTONS.md** (the contextual
button system + reverse-engineered binding format).

## Requirements
macOS · Python 3 · a SayoDevice O3C with icons pre-loaded (via [sayodevice.com](https://sayodevice.com))
