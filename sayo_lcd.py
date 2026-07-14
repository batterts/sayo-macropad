#!/usr/bin/env python3
"""
sayo_lcd — encode a 160x80 image into the SayoDevice LCD blob format
(palette + run-length, decoded 2026-07-12 from web-app WebHID captures).

Blob layout:
  06 01 <np>            header (np = number of palette colors)
  <w:2 LE=160> <h:2 LE=80>
  <field:2 LE = 0xA0 + (np-1)*4>
  00 00 00             reserved
  <palette: np * 2-byte LE RGB565>
  RLE tokens: [ff][count 1..255][palette_index]   (row-major, top->bottom)
"""
from PIL import Image

W, H = 160, 80

def rgb565(r, g, b):
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)

def encode(img, max_colors=16):
    """PIL image (any size) -> LCD blob bytes. Quantizes to <=max_colors."""
    img = img.convert("RGB")
    if img.size != (W, H):
        img = img.resize((W, H))
    # quantize to a small palette
    q = img.quantize(colors=max_colors, method=Image.MEDIANCUT).convert("RGB")
    px = list(q.getdata())  # row-major, W*H
    # build palette in order of first appearance
    pal_index = {}
    pal = []
    idx_stream = []
    for p in px:
        c = rgb565(*p)
        if c not in pal_index:
            pal_index[c] = len(pal)
            pal.append(c)
        idx_stream.append(pal_index[c])
    np = len(pal)
    # RLE the index stream: [ff][count<=255][index]
    rle = bytearray()
    i = 0
    n = len(idx_stream)
    while i < n:
        idx = idx_stream[i]
        run = 1
        while i + run < n and idx_stream[i + run] == idx and run < 255:
            run += 1
        rle += bytes([0xFF, run, idx])
        i += run
    # header: dims/field are BIG-endian; palette entries are LITTLE-endian RGB565
    field = 0xA0 + (np - 1) * 4
    blob = bytearray()
    blob += bytes([0x06, 0x01, np])
    blob += bytes([W >> 8, W & 0xFF])
    blob += bytes([H >> 8, H & 0xFF])
    blob += bytes([field >> 8, field & 0xFF])
    blob += bytes([0, 0, 0])
    for c in pal:
        blob += bytes([c & 0xFF, c >> 8])
    blob += rle
    return bytes(blob)

if __name__ == "__main__":
    import sys
    # self-test: reproduce the captured red/blue and solid-red blobs
    CAPTURED = {
        # 06 01 np | w:2 BE | h:2 BE | field:2 BE | 3 reserved | palette LE | RLE
        "lcd_test.png": "060102" "00a0" "0050" "00a4" "000000" "00f8" "1f00"
                        + "ffff00" * 25 + "ff1900" + "ffff01" * 25 + "ff1901",
        "lcd_red.png":  "060101" "00a0" "0050" "00a0" "000000" "00f8"
                        + "ffff00" * 50 + "ff3200",
    }
    ok = True
    for name, expect in CAPTURED.items():
        blob = encode(Image.open(name))
        got = blob.hex()
        match = (got == expect)
        ok &= match
        print(f"{name}: {'MATCH' if match else 'DIFF'} (len {len(blob)})")
        if not match:
            print("  expect:", expect[:80])
            print("  got:   ", got[:80])
            # show first diff
            for k in range(min(len(expect), len(got))):
                if expect[k] != got[k]:
                    print(f"  first diff at hex idx {k}: expect {expect[k:k+8]} got {got[k:k+8]}")
                    break
    print("SELF-TEST:", "PASS" if ok else "FAIL")


# ---- transport: select (show image N on layer L) over report 0x22 ----
def _chk(payload):
    d = payload + (b"\x00" if len(payload) % 2 else b"")
    s = sum(d[i] | (d[i + 1] << 8) for i in range(0, len(d), 2))
    return (s + 0x1222) & 0xFFFF

def build_select(layer, img):
    """Frame to display image index `img` (0-based) on screen layer `layer`."""
    p = bytes([0x3C, 0x00, 0x22, layer, 0x07, 0, 0, 0, img, 0x01, 0, 0, 0, 0, 0, 0, 0, 0xF0])
    c = _chk(p)
    return bytes([0x12, c & 0xFF, c >> 8]) + p

def send_report22(frame):
    """Send a wrapped frame on HID report 0x22 (the screen channel)."""
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from sayo_toolkit.upload import SayoLink
    link = SayoLink(verbose=False).open()
    d = link.dev
    payload = bytes([0x22]) + frame + bytes(1023 - len(frame))   # report id + 1023 data
    d.write(payload)
    link.close()

def show_image(img, layer=2):
    send_report22(build_select(layer, img))


# ---- transport: upload an image blob (cmd 0x20) over report 0x22 ----
def _wrap(payload):
    """payload = [len:2 LE][cmd...]; prepend [0x12][chk16 LE]. chk over payload."""
    c = _chk(payload)
    return bytes([0x12, c & 0xFF, c >> 8]) + payload

CHUNK = 1012

def build_upload(blob, base):
    """Frames to write `blob` at storage `base`: data chunks + finalize + commit."""
    frames = []
    for i in range(0, len(blob), CHUNK):
        data = blob[i:i + CHUNK]
        off = base + i
        ln = len(data) + 8                       # len = len(2)+cmd(2)+offset(4)+data
        payload = bytes([ln & 0xFF, ln >> 8, 0x20, 0x01]) + off.to_bytes(4, "little") + data
        frames.append(_wrap(payload))
    end = base + len(blob)
    fin = bytes([0x38, 0x00, 0x20, 0x01]) + end.to_bytes(4, "little") + bytes(56 - 8)  # len=56
    frames.append(_wrap(fin))
    commit = bytes([0x08, 0x00, 0x20, 0x01, 0xFF, 0xFF, 0xFF, 0xFF])                    # len=8
    frames.append(_wrap(commit))
    return frames

def upload_image_frames(dev, frames):
    """Write pre-built upload frames on an already-open hid device handle."""
    import time
    for f in frames:
        dev.write(bytes([0x22]) + f + bytes(1023 - len(f)))
        time.sleep(0.005)

def upload_image(img, base, max_colors=64):
    """Encode + upload an image at storage offset `base`. Opens its own handle."""
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from sayo_toolkit.upload import SayoLink
    blob = encode(img, max_colors=max_colors)
    frames = build_upload(blob, base)
    link = SayoLink(verbose=False).open()
    upload_image_frames(link.dev, frames)
    link.close()
    return blob


# ---- v2 encoder: raw 2-byte RGB565 run-stream (the REAL device format) ----
# Stream is row-major 160x80 pixels. Token: [ff][count 1..255][lo][hi] = `count`
# pixels of RGB565 color (lo,hi). All-runs output => every token starts 0xff, so the
# device decoder is never ambiguous with 0xff-containing literal colors.
def encode_v2(img):
    img = img.convert("RGB")
    if img.size != (W, H):
        img = img.resize((W, H))
    px = list(img.getdata())
    out = bytearray()
    i, n = 0, len(px)
    while i < n:
        c = px[i]
        col = rgb565(*c)
        run = 1
        while i + run < n and rgb565(*px[i + run]) == col and run < 255:
            run += 1
        out += bytes([0xFF, run, col & 0xFF, col >> 8])
        i += run
    return bytes(out)

def upload_image_v2(img, base):
    """Encode with the real 2-byte-run format and upload at storage offset `base`."""
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from sayo_toolkit.upload import SayoLink
    blob = encode_v2(img)
    frames = build_upload(blob, base)
    link = SayoLink(verbose=False).open()
    upload_image_frames(link.dev, frames)
    link.close()
    return blob


# ---- v3 encoder: the REAL on-device format (confirmed via flash readback) ----
# Header (12B): 06 01 np | w:2 BE | h:2 BE | 00 | field:3 LE | 00
#   field = payload size = len(palette) + len(pixel_stream)  (== image_size - 12)
# palette: np * 2-byte LE RGB565 (first-appearance order)
# pixel stream: palette INDICES, row-major; literal 1-byte idx OR run [ff][count][idx].
#   (idx 0xff is reserved as the run marker, so quantize to <=254 colors.)
def encode_v3(img, max_colors=254):
    img = img.convert("RGB")
    if img.size != (W, H):
        img = img.resize((W, H))
    q = img.quantize(colors=min(max_colors, 254), method=Image.MEDIANCUT).convert("RGB")
    px = list(q.getdata())
    pal_index, pal, idx = {}, [], []
    for p in px:
        c = rgb565(*p)
        if c not in pal_index:
            pal_index[c] = len(pal); pal.append(c)
        idx.append(pal_index[c])
    np_ = len(pal)
    # RLE the index stream: all-runs (every token [ff][count 1..255][idx]) -> unambiguous
    stream = bytearray()
    i, n = 0, len(idx)
    while i < n:
        v = idx[i]; run = 1
        while i + run < n and idx[i + run] == v and run < 255:
            run += 1
        stream += bytes([0xFF, run, v]); i += run
    palette = bytearray()
    for c in pal:
        palette += bytes([c & 0xFF, c >> 8])
    field = len(palette) + len(stream)
    hdr = bytes([0x06, 0x01, np_, W >> 8, W & 0xFF, H >> 8, H & 0xFF, 0x00,
                 field & 0xFF, (field >> 8) & 0xFF, (field >> 16) & 0xFF, 0x00])
    return hdr + bytes(palette) + bytes(stream)

def upload_images(images, base=0x0000):
    """Encode a LIST of images (v3), pack them sequentially from `base`, finalize+commit.
    Replaces the on-device image set; slot index = position in `images`."""
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from sayo_toolkit.upload import SayoLink
    blob = bytearray()
    offsets = []
    for im in images:
        offsets.append(base + len(blob))
        blob += encode_v3(im)
    frames = build_upload(bytes(blob), base)
    link = SayoLink(verbose=False).open()
    upload_image_frames(link.dev, frames)
    link.close()
    return offsets, len(blob)
