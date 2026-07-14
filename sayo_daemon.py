#!/usr/bin/env python3
"""
sayo-daemon — make the SayoDevice O3C follow the frontmost macOS app.

On each app switch it drives (host-side, no flash wear):
  - the LCD  -> selects the app's pre-loaded icon and shows it clean/full-screen
  - the LEDs -> sets the button colors for that app

It only SELECTS pre-loaded images (never uploads), so it never triggers the
transfer-mode "Loading" state. Edit sayo_config.json to map apps -> slot + color.

Usage:
  ./venv/bin/python sayo_daemon.py            # run the follow loop
  ./venv/bin/python sayo_daemon.py --once      # print current app + rule, exit
  ./venv/bin/python sayo_daemon.py --verbose
"""
import sys, os, json, time, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sayo_dev

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "sayo_config.json")


def load_config():
    with open(CONFIG) as f:
        return json.load(f)


def osa(script, timeout=2):
    try:
        return subprocess.check_output(["osascript", "-e", script], text=True,
                                       timeout=timeout).strip()
    except Exception:
        return ""


def frontmost_app():
    return osa('tell application "System Events" to get name of first process '
               'whose frontmost is true') or "<none>"


def browser_url(app):
    if app == "Safari":
        return osa('tell application "Safari" to get URL of current tab of front window')
    if app == "Google Chrome":
        return osa('tell application "Google Chrome" to get URL of active tab of front window')
    return ""


def resolve(app, cfg):
    """Return the matching rule dict (with label/slot/color) for `app`."""
    url = None
    for rule in cfg["rules"]:
        if app not in rule.get("match_app", []):
            continue
        if "match_url" in rule:
            if url is None:
                url = browser_url(app).lower()
            if rule["match_url"] not in url:
                continue
        return rule
    return cfg["default"]


def apply(rule, cfg, first_time, verbose=False):
    """Push the rule's icon + colors to the device. Returns True on success."""
    if not sayo_dev.device_present():
        if verbose:
            print("  (device not present, skipping)")
        return False
    try:
        with sayo_dev.Device() as dev:
            if first_time:
                dev.clear_overlays()      # blank counter/text layers once
            dev.show_image(rule["slot"])
            r, g, b = rule.get("color", [40, 40, 40])
            if cfg.get("button_script_enabled"):
                dev.set_app(rule.get("mode", 0), r, g, b)   # mode -> zone1, color -> sides
            else:
                dev.set_all_colors(r, g, b)                 # all buttons = icon color
        return True
    except sayo_dev.DeviceError:
        if verbose:
            print("  (device busy — web app connected?)")
        return False
    except Exception as e:
        if verbose:
            print(f"  (push failed: {e})")
        return False


def main(argv):
    cfg = load_config()
    verbose = "--verbose" in argv

    if "--once" in argv:
        app = frontmost_app()
        rule = resolve(app, cfg)
        print(f"{app!r} -> {rule['label']}  slot={rule['slot']}  color={rule.get('color')}")
        return

    print("sayo-daemon: following the frontmost app (Ctrl-C to stop)")
    last_label = None
    cleared = False
    while True:
        app = frontmost_app()
        rule = resolve(app, cfg)
        if rule["label"] != last_label:
            print(f"  {app!r} -> {rule['label']}  slot={rule['slot']}")
            ok = apply(rule, cfg, first_time=not cleared, verbose=verbose)
            if ok:
                cleared = True
                last_label = rule["label"]
        time.sleep(cfg.get("poll_seconds", 0.5))


if __name__ == "__main__":
    main(sys.argv)
