#!/usr/bin/env python3
"""
sayoc — local SayoDevice v3 script compiler / disassembler / backup inspector.

  sayoc asm   FILE.v3          compile assembly -> hex bytecode (+ optional -o file)
  sayoc dis   HEX|FILE.bin     disassemble bytecode (hex string or binary file)
  sayoc dis-json FILE.json     disassemble the "bytecode" field of a script.json
  sayoc bak   FILE.sayobak     inspect a backup file; dump/disassemble scripts
  sayoc selftest               validate the ISA against the known-good samples

No device or network needed for any of these.
"""
import argparse
import binascii
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sayo_toolkit import assemble, disassemble, AsmError, SayobakFile


def _read_hex_or_file(arg):
    if os.path.isfile(arg):
        with open(arg, "rb") as f:
            return f.read()
    cleaned = "".join(arg.split()).replace("0x", "")
    return binascii.unhexlify(cleaned)


def cmd_asm(args):
    with open(args.file) as f:
        code = assemble(f.read())
    if args.o:
        with open(args.o, "wb") as f:
            f.write(code)
        print(f"wrote {len(code)} bytes -> {args.o}")
    print(code.hex())
    if args.show:
        print("\n" + disassemble(code))
    return 0


def cmd_dis(args):
    code = _read_hex_or_file(args.input)
    print(disassemble(code, show_addr=not args.no_addr,
                      show_bytes=not args.no_bytes))
    return 0


def cmd_dis_json(args):
    with open(args.file) as f:
        obj = json.load(f)
    code = binascii.unhexlify(obj["bytecode"])
    print(f"# {args.file}: {obj.get('name','')}  ({len(code)} bytes)")
    print(disassemble(code))
    return 0


def cmd_bak(args):
    sf = SayobakFile.load(args.file)
    recs = sf.records()
    print(f"# {os.path.basename(args.file)} — {len(recs)} record(s)")
    for r in recs:
        print(f"  record @0x{r.offset:04X}: cmd=0x{r.cmd:02X} page=0x{r.page:02X} "
              f"len={r.length}")
    scripts = list(sf.iter_scripts())
    if scripts:
        print()
        for slot, code in scripts:
            print(f"## script slot 0x{slot:02X} ({len(code)} bytes)")
            print(f"   hex: {code.hex()}")
            print(disassemble(code, base=0))
            print()
    return 0


# The two ground-truth samples from this project.
SAMPLE_DEVICE_HEX = "f86e0414110e0623190e0623340 4ff".replace(" ", "")
SAMPLE_LOCAL_HEX = ("f86e04110e0623190e06231105062319050623110f0623190f0623112e0623"
                    "192e06233404112c0623192cff")

# script.v3 as it *should* compile (the SYS_KBLED reader that types "KBL=<value> ").
SAMPLE_SOURCE = """
    MODE_JOG
    MOV R0 SYS_KBLED
    PRESS_GK hidkey_K  ; K
    SLEEP 35
    RELEASE_GK hidkey_K
    SLEEP 35
    PRESS_GK hidkey_B  ; B
    SLEEP 35
    RELEASE_GK hidkey_B
    SLEEP 35
    PRESS_GK hidkey_L  ; L
    SLEEP 35
    RELEASE_GK hidkey_L
    SLEEP 35
    PRESS_GK hidkey_Equal  ; =
    SLEEP 35
    RELEASE_GK hidkey_Equal
    SLEEP 35
    PRINT_REG R0
    PRESS_GK hidkey_Space
    SLEEP 35
    RELEASE_GK hidkey_Space
    EXIT
"""


def cmd_selftest(_args):
    ok = True

    # 1. round-trip the device bytecode: dis then re-assemble must match.
    dev = binascii.unhexlify(SAMPLE_DEVICE_HEX)
    print("== device 'debug' script (scripts.sayobak) ==")
    print(disassemble(dev))
    reasm = assemble(_strip_addr(disassemble(dev, show_addr=False, show_bytes=False)))
    print(f"round-trip: {'OK' if reasm == dev else 'MISMATCH'} "
          f"({reasm.hex()} vs {dev.hex()})")
    ok &= reasm == dev

    # 2. compile script.v3 and confirm it is well-formed and self-consistent.
    print("\n== compile script.v3 (the intended KBL= reader) ==")
    good = assemble(SAMPLE_SOURCE)
    print(f"compiled {len(good)} bytes: {good.hex()}")
    rt = assemble(_strip_addr(disassemble(good, show_addr=False, show_bytes=False)))
    print(f"round-trip: {'OK' if rt == good else 'MISMATCH'}")
    ok &= rt == good

    # 3. show why the shipped script.json is corrupt.
    print("\n== shipped script.json bytecode (as the device parses it) ==")
    local = binascii.unhexlify(SAMPLE_LOCAL_HEX)
    print(disassemble(local))
    print("\nDiagnosis: the MOV that should read SYS_KBLED (reg 0x14) is one byte")
    print("short — it reads 0x11 (=reg B) and swallows the first PRESS_GK's opcode,")
    print("desyncing the stream (note the stray SLEEP_RAND_U16 and the RELEASE with")
    print("no matching PRESS). The correctly-compiled version above avoids this.")

    print(f"\nSELFTEST: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def _strip_addr(text):
    # disassemble(show_addr=False, show_bytes=False) still appends "; ..." notes;
    # keep only the instruction part for re-assembly.
    lines = []
    for ln in text.splitlines():
        lines.append(ln.split(";", 1)[0].strip())
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd")

    a = sub.add_parser("asm", help="assemble .v3 -> bytecode")
    a.add_argument("file")
    a.add_argument("-o", help="write raw bytecode to this file")
    a.add_argument("--show", action="store_true", help="also print disassembly")
    a.set_defaults(func=cmd_asm)

    d = sub.add_parser("dis", help="disassemble hex or binary")
    d.add_argument("input")
    d.add_argument("--no-bytes", action="store_true")
    d.add_argument("--no-addr", action="store_true",
                   help="omit address column (output is re-assemblable)")
    d.set_defaults(func=cmd_dis)

    dj = sub.add_parser("dis-json", help="disassemble a script.json bytecode field")
    dj.add_argument("file")
    dj.set_defaults(func=cmd_dis_json)

    b = sub.add_parser("bak", help="inspect a .sayobak backup")
    b.add_argument("file")
    b.set_defaults(func=cmd_bak)

    s = sub.add_parser("selftest", help="validate ISA against known samples")
    s.set_defaults(func=cmd_selftest)

    args = p.parse_args()
    if not args.cmd:
        p.print_help()
        return 1
    try:
        return args.func(args)
    except AsmError as e:
        print(f"assembly error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
