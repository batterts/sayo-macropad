#!/usr/bin/env python3
"""Composite an app icon centered on a black 160x80 canvas (small icon, black bg ->
tiny RLE blob + clean layered look). Plus device setup: upload a set + clean screen."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image
import sayo_lcd
from sayo_toolkit.upload import SayoLink

W, H = 160, 80

def centered(path, size=64):
    """App icon scaled to `size`x`size`, centered on a black 160x80 canvas."""
    icon = Image.open(path).convert("RGBA").resize((size, size))
    canvas = Image.new("RGB", (W, H), (0, 0, 0))
    canvas.paste(icon, ((W - size) // 2, (H - size) // 2), icon)  # alpha as mask
    return canvas

def clear_overlays(d, keep_layer=2, layers=range(0, 12)):
    """Blank all main-screen overlay layers except the image layer (live format)."""
    for idx in layers:
        if idx == keep_layer:
            continue
        f = sayo_lcd._wrap(bytes([0x3C, 0x00, 0x22, idx]) + bytes(56))
        d.write(bytes([0x22]) + f + bytes(1023 - len(f)))
        time.sleep(0.05)

def select(d, img, layer=2):
    sel = sayo_lcd.build_select(layer, img)
    d.write(bytes([0x22]) + sel + bytes(1023 - len(sel)))
