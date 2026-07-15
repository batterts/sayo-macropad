# Factory-reset recovery

A knob-hold factory reset wipes calibration + bindings + script, and **restores the
factory screen layers** (built-in images, animations, ASCII text, press counters) that
otherwise fight our custom app icons. Full recovery is three steps:

## 1. Restore the blank screen backup (web app)
`sayodevice.com` → connect → **Backup & Restore** → **Restore** → pick
**`sayobk-blank.sayobak`** (in this repo).

This is a full-device backup with every screen layer's default image/animation/text/
counter **unassigned** (Bootup / Main / Sleep, all Fn layers), leaving a clean screen
with just a Custom Images layer — so our uploaded icons display without the counter
overlay. It carries no passwords/personal data (verified: only factory osu! bootup text).

## 2. Calibrate the keys (web app)
Still connected: **Calibrate** the analog keys (hands **off** the keys while it runs).
Calibration is sensor-specific and can't be safely written from the host — this is the
one irreducible manual step. It also stops the `x`/`z`/`c` phantom typing.

## 3. Load everything else (one command)
Disconnect the web app, then:
```bash
cd ~/sayo/sayo-macropad 2>/dev/null || cd ~/code/SayoDevice-Shauny-GPT-version
./restore.sh
```
`restore.sh` re-flashes the button script, re-asserts the 6 run-script bindings, and
re-uploads the 7 app icons — then restarts the daemon. Switch apps to confirm the LCD
icon + LED colors + contextual buttons all follow.

---
**Why calibration/screen need the web app but everything else doesn't:** calibration is
per-sensor analog data (unsafe to guess), and the factory screen layout is baked into a
device backup. Script, bindings, and image *content* all use protocols we reversed, so
`restore.sh` handles them. See `BUTTONS.md` for the binding/script details.
