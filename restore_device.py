#!/usr/bin/env python3
"""
Restore the SayoDevice after a factory reset (run via restore.sh, which stops/starts
the daemon and frees the device first).

Restores everything that's safe to write from the host:
  1. button script  (modes.bin -> script slot 0)
  2. button bindings (keys 0-5 -> run script slot 0, arg0=key# -> V0)
  3. app icons       (7 PNGs -> image slots 0-6, packed from offset 0)

NOT restored here: key CALIBRATION (sensor-specific; do it once via sayodevice.com ->
Calibrate). Icons are cosmetic — if their upload fails, buttons still work and you can
drag the PNGs in via the web app.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sayo_toolkit.upload import upload_script, SayoLink, build_packet
import sayo_lcd, sayo_icons

# slot -> icon file (MUST match the slots in sayo_config.json)
SLOT_ICON = {0: "MacVim", 1: "Safari", 2: "iTerm", 3: "Chrome",
             4: "IntelliJ", 5: "YouTube", 6: "Default"}

# the run-script keybinding template (keymode 0x40=scripts, slot 0); arg0 at [20] -> V0
_BIND = bytearray.fromhex("01000000e803b80b0807080764000000400000000000000000000000001d")
_BIND += bytes(56 - len(_BIND))


def flash_script():
    for a in range(3):
        try:
            upload_script(open("modes.bin", "rb").read(), do_write=True,
                          name="modes", slot=0, verbose=False)
            print("   script flashed (slot 0)")
            return True
        except Exception as e:
            print(f"   retry {a}: {e}"); time.sleep(1.5)
    print("   SCRIPT FLASH FAILED"); return False


def bind_keys():
    link = SayoLink(verbose=False).open(); d = link.dev
    try:
        for key in range(6):
            data = bytearray(_BIND); data[20] = key       # arg0 = key# -> V0
            p = bytes([0x3C, 0x00, 0x10, key]) + bytes(data)
            f = sayo_lcd._wrap(p)
            d.write(bytes([0x22]) + f + bytes(1023 - len(f))); time.sleep(0.08)
        d.write(build_packet(4, [0x72, 0x96])); time.sleep(0.05)   # save
        try: d.read(64, 300)
        except OSError: pass
    finally:
        link.close()
    print("   bound keys 0-5 -> run script slot 0 (V0=key#)")


def upload_icons():
    imgs = [sayo_icons.centered(f"icons/{SLOT_ICON[i]}.png", size=72)
            for i in range(len(SLOT_ICON))]
    _, total = sayo_lcd.upload_images(imgs, base=0x0000)
    print(f"   uploaded {len(imgs)} icons ({total} bytes) to slots 0-6")


def main():
    print("1/3 flashing button script...")
    flash_script(); time.sleep(0.4)
    print("2/3 re-asserting button bindings...")
    bind_keys(); time.sleep(0.4)
    print("3/3 uploading app icons...")
    try:
        upload_icons()
    except Exception as e:
        print(f"   ICON UPLOAD FAILED ({e}) — buttons still work; drag PNGs in via "
              f"sayodevice.com if the LCD stays blank")
    print("restore complete.")


if __name__ == "__main__":
    main()
