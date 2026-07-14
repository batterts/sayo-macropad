# sayo_toolkit — local SayoDevice scripting-VM toolchain

A dependency-free, **offline** assembler / disassembler / backup-parser for the
SayoDevice O3C on-device scripting VM (v3 bytecode), plus a verifying HID
uploader. Built so you can author and inspect scripts locally instead of trusting
the vendor's China-hosted web tool.

Everything except `upload.py` is pure Python (no `hid`, no network).

## Why this exists — the bug we found

The device's stored `debug` script (in `../sayo backups/scripts.sayobak`)
disassembles cleanly:

```
MODE_JOG
MOV R0 SYS_KBLED          ; 6e 04 14   (SYS_KBLED = register index 0x14)
PRESS_GK hidkey_K ...
PRINT_REG R0
EXIT
```

The elaborated local build (`../script.json`, produced by the vendor tool) is the
**same program with one byte deleted** — the `0x14` operand of that `MOV`:

```
correct : f8 6e 04 14 11 0e 06 23 ...
shipped : f8 6e 04    11 0e 06 23 ...   <- missing 0x14
```

That dropped byte desyncs the whole instruction stream (the device reads a bogus
9-second `SLEEP_RAND_U16` and a `RELEASE` with no matching `PRESS`). That is why
uploading the fuller custom script "didn't take." Recompiling `script.v3` with
this toolkit's assembler emits the correct bytes.

Confirm it yourself:

```
python3 ../sayoc.py selftest          # round-trips the real samples, PASS
python3 ../sayoc.py dis-json ../script.json   # shows the corrupt stream
python3 ../sayoc.py asm ../script.v3           # emits the CORRECT bytecode
```

## CLI (`../sayoc.py`)

| command | what it does |
|---|---|
| `sayoc asm FILE.v3 [-o out.bin] [--show]` | assemble source → bytecode |
| `sayoc dis HEX-or-FILE` | disassemble bytecode |
| `sayoc dis-json script.json` | disassemble a `script.json` bytecode field |
| `sayoc bak scripts.sayobak` | list backup records; dump/disassemble scripts |
| `sayoc selftest` | validate the ISA against the project's known samples |

## Uploading to the device (`upload.py`, needs hidapi)

The wire protocol is now **confirmed** — `upload.py` faithfully reimplements the
official `Sayo_CLI` O2 protocol (frame, checksum, 54-byte script paging, save).
See `PROTOCOL.md`. Run with the venv that has `hid`:

```
./venv/bin/python -m sayo_toolkit.upload list                     # find interface
./venv/bin/python -m sayo_toolkit.upload upload script_fixed.bin  # DRY-RUN (default)
./venv/bin/python -m sayo_toolkit.upload upload script_fixed.bin --write
```

**Safety model.** `upload` is **dry-run by default** and prints the exact packets.
The real upload writes bytecode (cmd `0xF0`) then persists (cmd `4`, save). Nothing
reaches flash until that final save packet, so if anything looks wrong a **replug
restores the device** (config is reloaded from flash on power-up).

**Verified end-to-end.** Uploading `script_fixed.bin` returns `OK` ACKs and a
read-back of the 4 KB script region byte-matches the upload. Reads/ACKs work on
macOS with a valid checksum (early "silent" probes were just malformed frames).
You can also confirm by pressing the mapped key — the script types `KBL=<value>`.

## Files

- `isa.py` — opcode table, register indices, HID keycodes (from `script.md`)
- `assembler.py` — `assemble()` / `disassemble()`
- `sayobak.py` — `.sayobak` container reader
- `upload.py` — verifying HID uploader (dry-run default)

## Notes / caveats

- Register indices are inferred from list position in `script.md`; confirmed by
  two samples (`R0`=4, `SYS_KBLED`=0x14). Uncommon registers are unverified.
- `label` operands are 16-bit **big-endian** per the manual; all other immediates
  are little-endian.
- The manual lists `JFNZ` with one operand but length 3; treated as `reg, reg`
  (like `JFZ`).
