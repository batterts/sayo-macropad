#!/usr/bin/env python3
"""
sayo_show — manually drive the LCD/LEDs for testing & mapping your icons.

  ./venv/bin/python sayo_show.py 3            # show image slot 3 (clean, full-screen)
  ./venv/bin/python sayo_show.py 3 255 0 0     # slot 3 + red LEDs
  ./venv/bin/python sayo_show.py tour          # cycle 0..6 with a pause, to label them
  ./venv/bin/python sayo_show.py app safari     # apply the config rule for a given label
"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sayo_dev

HERE = os.path.dirname(os.path.abspath(__file__))


def show(slot, color=None):
    with sayo_dev.Device() as dev:
        dev.show_clean(slot)
        if color:
            dev.set_all_colors(*color)


def tour(lo=0, hi=6, pause=2.5):
    for slot in range(lo, hi + 1):
        print(f"showing slot {slot} ...")
        with sayo_dev.Device() as dev:
            dev.show_clean(slot)
        time.sleep(pause)
    print("done — note which app each slot is, then edit sayo_config.json")


def main(argv):
    if not argv:
        print(__doc__)
        return
    cmd = argv[0]
    if cmd == "tour":
        tour()
    elif cmd == "app":
        cfg = json.load(open(os.path.join(HERE, "sayo_config.json")))
        label = argv[1]
        rule = next((r for r in cfg["rules"] + [cfg["default"]] if r["label"] == label), None)
        if not rule:
            print("no rule labelled", label); return
        show(rule["slot"], rule.get("color"))
        print(f"applied {label}: slot {rule['slot']} color {rule.get('color')}")
    else:
        slot = int(cmd)
        color = tuple(int(x) for x in argv[1:4]) if len(argv) >= 4 else None
        show(slot, color)
        print(f"showing slot {slot}" + (f" color {color}" if color else ""))


if __name__ == "__main__":
    main(sys.argv[1:])
