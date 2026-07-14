#!/usr/bin/env python3
"""
sayo-state — push a small state value into the SayoDevice, wear-free.

Usage:  python3 sayo_state.py <recording 0|1>

Writes a color into lighting zone 2 (the right/Play button LED) via cmd 16, LIVE
(no save, no flash wear). A device script reads it back with LED_CTRL 2 +
SELECTED_LED_COL. This is the host->device state channel proven on 2026-07-12.

Encoding (this proof): recording -> zone2 low byte = 0xAA (nonzero); idle -> 0.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sayo_toolkit.upload import build_packet, SayoLink

STATE_ZONE = 2   # right/Play button LED carries the state

def set_zone_color(zone, r, g, b):
    link = SayoLink(verbose=False).open()
    d = link.dev
    d.set_nonblocking(True)
    while d.read(64, 0):          # drain telemetry
        pass
    d.set_nonblocking(False)
    # cmd 16 static-mode zone write; color goes at data[3:6]; low byte of the
    # register the script reads == r (data[3]).
    data = [0x00, 0x00, 0x01, r, g, b, 0x64, 0x64, 0x01] + [0] * 40
    d.write(build_packet(16, [1, zone, 0] + data))
    d.read(64, 500)
    link.close()

def main(argv):
    recording = len(argv) > 1 and argv[1].lower() not in ("0", "off", "false", "")
    if recording:
        set_zone_color(STATE_ZONE, 0xAA, 0x00, 0x00)   # nonzero -> "recording"
    else:
        set_zone_color(STATE_ZONE, 0x00, 0x00, 0x00)   # zero -> "idle"

if __name__ == "__main__":
    main(sys.argv)
