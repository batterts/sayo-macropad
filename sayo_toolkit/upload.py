"""
Device I/O for the SayoDevice O2 protocol — faithful reimplementation of the
official Sayo_CLI (github.com/Sayobot/Sayo_CLI, o2_protocol.cpp), so we can push
a locally-compiled script without the vendor's hosted tool.

Requires hidapi:  ./venv/bin/python -m sayo_toolkit.upload ...

Wire format (report 0x02, vendor page 0xFF00), 64-byte packet:
    byte[0]   = id        (0x02, the report id)
    byte[1]   = cmd
    byte[2]   = data_len
    byte[3..] = data[data_len]
    byte[data_len+3] = checksum = (sum of bytes[0 .. data_len+2]) & 0xFF
The device ACKs by replying with the same packet shape and cmd == 0 on success.

Script upload (verbatim from Sayo_CLI O2Protocol::Script write path):
    cmd 0xF0, data = [addr_h, addr_l, <=54 bytecode bytes]; page the compiled
    bytecode in 54-byte chunks from address 0; append FF FF only if the program
    doesn't already end in 0xFF; Sleep(5ms) between chunks; then Save (cmd 4,
    payload [0x72, 0x96]).

Reads/ACKs work on macOS as long as the frame is valid (correct checksum) —
verified by uploading a script and reading the 4 KB region back byte-for-byte.
Nothing persists without the explicit Save.
"""
import sys
import time

try:
    import hid
except ImportError:  # pragma: no cover
    hid = None

VENDOR_ID = 0x8089
REPORT_SIZE = 64
CHUNK = 54                      # bytecode bytes per script packet (Sayo_CLI)

CMD_SAVE = 0x04                 # payload [0x72, 0x96]
CMD_SCRIPT = 0xF0              # bytecode write/read (addr_h, addr_l, data)
CMD_SCRIPT_SW = 0xF1          # slot name/select (pattern, number, name[32])
SAVE_MAGIC = (0x72, 0x96)


class DeviceError(Exception):
    pass


def build_packet(cmd, data=()):
    """Return a 64-byte O2 packet list with the checksum in place."""
    data = list(data)
    if len(data) > REPORT_SIZE - 4:
        raise DeviceError(f"data too long for one packet: {len(data)}")
    pkt = [0x02, cmd & 0xFF, len(data)] + data
    checksum = sum(pkt) & 0xFF          # sum of id+cmd+len+data == bytes[0..len+2]
    pkt.append(checksum)                # lands at index len+3
    pkt += [0] * (REPORT_SIZE - len(pkt))
    return pkt


def script_packets(bytecode, verbose=True):
    """Yield ('label', packet) for a full script upload of `bytecode`
    (raw compiled opcodes, e.g. from sayoc asm)."""
    code = bytearray(bytecode)
    if not code or code[-1] != 0xFF:    # Sayo_CLI appends FF FF terminator
        code += b"\xff\xff"
    for off in range(0, len(code), CHUNK):
        chunk = code[off:off + CHUNK]
        data = [off >> 8, off & 0xFF] + list(chunk)     # addr_h, addr_l, chunk
        yield (f"data@{off}", build_packet(CMD_SCRIPT, data))
    yield ("save", build_packet(CMD_SAVE, SAVE_MAGIC))


class SayoLink:
    def __init__(self, verbose=True):
        if hid is None:
            raise DeviceError("hidapi not installed (use ./venv/bin/python)")
        self.verbose = verbose
        self.dev = None

    def _vendor_path(self):
        best = None
        for d in hid.enumerate():
            if d.get("vendor_id") != VENDOR_ID:
                continue
            up = d.get("usage_page") or 0
            score = 2 if up == 0xFF00 else (1 if up >= 0xFF00 else 0)
            if best is None or score > best[0]:
                best = (score, d["path"])
        return best[1] if best else None

    def open(self, path=None):
        path = path or self._vendor_path()
        if not path:
            raise DeviceError("SayoDevice not found (plugged in?)")
        self.dev = hid.device()
        self.dev.open_path(path)
        return self

    def close(self):
        if self.dev:
            self.dev.close(); self.dev = None

    def __enter__(self): return self.open()
    def __exit__(self, *a): self.close()

    def _log(self, m):
        if self.verbose: print(f"[link] {m}", file=sys.stderr)

    def write_packet(self, pkt):
        n = self.dev.write(pkt)
        if n <= 0:
            raise DeviceError("hid write returned <= 0")
        return n

    def read_ack(self, timeout_ms=1000):
        """Return the device's reply packet (cmd==0 on success), or None on
        timeout. Works with a valid frame; a bad checksum yields no reply."""
        self.dev.set_nonblocking(False)
        data = self.dev.read(REPORT_SIZE, timeout_ms)
        return bytes(data) if data else None


def upload_script(bytecode, do_write=False, verbose=True, name=None, slot=None):
    """Upload compiled `bytecode`. Dry-run by default: prints the exact packets
    and sends nothing. Set do_write=True to actually transmit.

    Nothing persists to flash until the final Save packet; a replug restores the
    device if anything looks wrong.
    """
    packets = list(script_packets(bytecode, verbose))
    if slot is not None and name is not None:
        namebytes = list(name.encode("ascii", "ignore")[:32]) + [0] * 32
        sw = [1, slot & 0xFF] + namebytes[:32]          # pattern=1(write), number, name[32]
        packets.insert(0, ("name_slot", build_packet(CMD_SCRIPT_SW, sw)))

    if not do_write:
        print("# DRY-RUN — nothing sent. Packets:")
        for label, pkt in packets:
            used = pkt[2] + 4
            print(f"  {label:10} {bytes(pkt[:used]).hex()}")
        print(f"# {len(packets)} packets. Re-run with --write to transmit "
              f"(no persistence until the trailing 'save').")
        return packets

    link = SayoLink(verbose).open()
    try:
        for label, pkt in packets:
            link.write_packet(pkt)
            time.sleep(0.005)                            # Sleep(5) in Sayo_CLI
            ack = link.read_ack()
            status = "no-ack(macOS?)" if ack is None else \
                     ("OK" if len(ack) > 1 and ack[1] == 0 else f"cmd={ack[1] if len(ack)>1 else '?'}")
            link._log(f"{label}: {status}")
        link._log("upload sequence complete (verify by pressing the key)")
    finally:
        link.close()
    return packets


def _main(argv):
    import argparse, os
    p = argparse.ArgumentParser(description="SayoDevice script uploader (O2 protocol)")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("list", help="list SayoDevice vendor interfaces")
    u = sub.add_parser("upload", help="upload a .bin/hex script (dry-run default)")
    u.add_argument("input", help="raw .bin file or hex string of compiled bytecode")
    u.add_argument("--write", action="store_true", help="actually transmit")
    u.add_argument("--name", help="optional: name the slot (with --slot)")
    u.add_argument("--slot", type=int, help="optional: script slot number to name")
    args = p.parse_args(argv)

    if args.cmd == "list":
        for d in hid.enumerate():
            if d.get("vendor_id") == VENDOR_ID:
                print(hex(d["vendor_id"]), hex(d["product_id"]),
                      f"page={hex(d.get('usage_page') or 0)}",
                      repr(d.get("product_string")), d.get("path"))
    elif args.cmd == "upload":
        code = open(args.input, "rb").read() if os.path.isfile(args.input) \
               else bytes.fromhex(args.input)
        upload_script(code, do_write=args.write, name=args.name, slot=args.slot)
    else:
        p.print_help(); return 1
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
