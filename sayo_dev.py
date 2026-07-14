#!/usr/bin/env python3
"""
sayo_dev — high-level, robust device operations for the app-aware macropad.

Primitives proven this session:
  - LCD: `select` an image onto a screen layer + clear the overlay layers so the
    image shows clean and PERSISTS (device renders it from flash config).
  - LEDs: wear-free `cmd 16` lighting-zone colors (no flash write).

The daemon only ever SELECTS pre-loaded images (never uploads), which avoids the
transfer-mode wedging that uploads cause. Images are loaded once via the web app
(or sayo_lcd.upload_images for a fresh set).
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sayo_lcd
from sayo_toolkit.upload import build_packet, SayoLink, DeviceError

IMAGE_LAYER = 2                       # layer the icon lives on
OVERLAY_LAYERS = [0, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11]  # counter/text layers to blank


class Device:
    """Context-managed device handle with the app-aware operations."""
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.link = None
        self.dev = None

    def __enter__(self):
        self.link = SayoLink(verbose=False).open()
        self.dev = self.link.dev
        self._drain()
        return self

    def __exit__(self, *a):
        try:
            if self.link:
                self.link.close()
        except Exception:
            pass

    def _drain(self):
        self.dev.set_nonblocking(True)
        try:
            while self.dev.read(64, 0):
                pass
        except OSError:
            pass
        self.dev.set_nonblocking(False)

    def _send22(self, payload):
        """Send a report-0x22 frame (auto-wrapped + checksummed)."""
        f = sayo_lcd._wrap(payload)
        self.dev.write(bytes([0x22]) + f + bytes(1023 - len(f)))

    # ---- LCD ----
    def clear_overlays(self, keep=IMAGE_LAYER):
        for idx in OVERLAY_LAYERS:
            if idx == keep:
                continue
            self._send22(bytes([0x3C, 0x00, 0x22, idx]) + bytes(56))
            time.sleep(0.04)

    def show_image(self, slot, layer=IMAGE_LAYER):
        sel = sayo_lcd.build_select(layer, slot)
        self.dev.write(bytes([0x22]) + sel + bytes(1023 - len(sel)))

    def show_clean(self, slot):
        """Blank overlays then show the icon full-screen and clean."""
        self.clear_overlays()
        self.show_image(slot)

    # ---- LEDs (wear-free cmd 16 lighting zones) ----
    def set_zone(self, zone, r, g, b):
        data = [0x00, 0x00, 0x01, r, g, b, 0x64, 0x64, 0x01] + [0] * 40
        self.dev.write(build_packet(16, [1, zone, 0] + data))
        try:
            self.dev.read(64, 200)
        except OSError:
            pass

    def set_all_colors(self, r, g, b, zones=(0, 1, 2)):
        for z in zones:
            self.set_zone(z, r, g, b)

    def set_app(self, mode, r, g, b):
        """Side buttons (zones 0,2) = icon color; middle button (zone 1) carries the
        mode ID in its red channel so the on-device button-script can branch on it."""
        self.set_zone(1, int(mode) & 0xFF, 0, 0)   # mode carrier (reads as ~dark)
        self.set_zone(0, r, g, b)
        self.set_zone(2, r, g, b)


def device_present():
    import hid
    return any(d["vendor_id"] == 0x8089 for d in hid.enumerate())
