# SayoDevice O3C — HID wire protocol (O2 protocol)

Authoritatively reconstructed from the **official** `Sayo_CLI`
(github.com/Sayobot/Sayo_CLI, `o2_protocol.cpp` / `o2_protocol.h`), cross-checked
against the v3 tool's `main.json` + `run.log` and the live device's HID report
descriptor. `sayo_toolkit/upload.py` reimplements this faithfully.

## Transport

- VID `0x8089`, PID `0x0009`. Config = **HID report `0x02`**, vendor usage page
  `0xFF00`, interface 1 / collection 01. Output + Input reports (no Feature).
- Reports `0x21`/`0x22` (pages `0xFF11`/`0xFF12`) are the v2 "high-speed" +
  telemetry channels — they stream status and were the source of the transient
  LCD/LED glitch during probing (volatile only; a replug restores).

## Packet format (64 bytes) — `o2_hid_data`

```
byte[0]            id        = 0x02 (report id)
byte[1]            cmd
byte[2]            data_len
byte[3 .. 3+len-1] data[data_len]
byte[data_len+3]   checksum  = (sum of bytes[0 .. data_len+2]) & 0xFF
(padding to 64)
```

The device ACKs with the same shape and **`cmd == 0` on success** (non-zero =
error code), read back with `hid_read`. This works on macOS **as long as the
frame is valid** (correct checksum) — verified by uploading a script and reading
the 4 KB region back byte-for-byte. Malformed frames get no reply (which is why
the early probes looked "silent"); they are not a platform limitation.

## Command codes

`6`=buttons, `7`=lighting, `8`=dev_name, `11`=password, `12`=strings,
`16/17`=lights v2 / color-table, `22`=key config, **`0xF0`(240)=script bytecode**,
**`0xF1`(241)=script slot name/select**, `242`=script autostart, `248/249`=kb
lock/unlock, `252`=option bytes, `0xFE`(254)=dev_id (VID/PID). The device's own
support list (`run.log`): `22,4,8,11,12,16,17,48,49,50,51,240,241,248,252,254,255`.

Read vs write is a **`pattern` byte** (0=read, 1=write) that is the first data
byte for keyed commands (`key`, `script_sw`, `api`, ...).

## Save — cmd 4

.



```
[02][04][02][0x72][0x96][checksum]      # checksum = 0x10
```
Nothing persists to flash until this is sent. (This is why every probe during
reversing was safe: no Save was ever issued.)

## Script upload — cmd 0xF0 (verbatim algorithm)

1. Compile steps to bytecode (opcode + operands). `script_step_len[]` in the CLI
   matches `isa.py` instruction lengths exactly — independent confirmation of our
   assembler.
2. If the program does not already end in `0xFF`, append `FF FF`.
3. Page the bytecode in **54-byte chunks from address 0**:
   ```
   data = [addr_h, addr_l, <=54 bytecode bytes]
   packet = [02][F0][len(data)][data...][checksum]
   Sleep(5ms); read ACK (cmd==0)
   ```
4. `Save` (cmd 4) to persist.

`script_sw` (cmd 0xF1) write names a slot: `[pattern=1][number][name[32]]`,
`data_len=34`. Reads use `pattern=0` and iterate `number` until the device
returns a non-zero cmd.

### Example (our fixed SYS_KBLED reader, 45 bytes, already ends in 0xFF)
```
data@0  02 f0 2f 00 00 <45 bytecode bytes> 11
save    02 04 02 72 96 10
```

## Firmware

`sayo_firmware.bin` (17904 B, 2020) is **encrypted** (entropy 7.99/8, no RISC-V
reset vector, no strings). Not statically analyzable without the device key and
likely stale. A real dump needs live SWD (WCH-Link).
