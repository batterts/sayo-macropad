"""
Reader for SayoDevice ".sayobak" backup files (the per-component exports the
vendor web tool produces).

Layout (reverse-engineered from the backups in ../sayo backups/):

  offset 0x00 : 32-byte magic  "Sayo Device Backup File 1.0\0" (null-padded)
  offset 0x40 : one or more records, each:
                  u8   cmd      (HID command/report code, e.g. 0x09 = read block)
                  u8   page     (block/slot index)
                  u8   pad      (0x00)
                  u32  length   (little-endian, payload size in bytes)
                  ...  payload  (length bytes)

Confirmed against:
  deviceoptions.sayobak : 09 03 00 | 26 00 00 00 -> 38-byte payload  (file 109 = 64+7+38)
  scripts.sayobak       : 09 1a 00 | 00 10 00 00 -> 4096-byte payload (the 4 KB code region)

For a script code region, the used bytecode sits at the start and the rest is
zero padding; `iter_scripts()` trims to the program body.
"""

from dataclasses import dataclass

MAGIC = b"Sayo Device Backup File 1.0"
HEADER_SIZE = 0x40
RECORD_PREFIX = 7          # u8 cmd + u8 page + u8 pad + u32 len


class SayobakError(Exception):
    pass


@dataclass
class Record:
    cmd: int
    page: int
    length: int
    payload: bytes
    offset: int            # absolute offset of this record in the file


class SayobakFile:
    def __init__(self, data: bytes):
        if data[:len(MAGIC)] != MAGIC:
            raise SayobakError("not a Sayo backup file (bad magic)")
        self.data = data
        self.payload = data[HEADER_SIZE:]

    @classmethod
    def load(cls, path):
        with open(path, "rb") as f:
            return cls(f.read())

    def records(self):
        """Best-effort walk of the record list.

        The first record after the magic header is reliable across every sample
        file; later records in multi-block components (keybinding, scriptnames)
        use a looser layout, so we stop if a length would overrun the file.
        """
        out = []
        pos = HEADER_SIZE
        data = self.data
        while pos + RECORD_PREFIX <= len(data):
            cmd = data[pos]
            page = data[pos + 1]
            length = int.from_bytes(data[pos + 3:pos + 7], "little")
            body_start = pos + RECORD_PREFIX
            if length == 0 or body_start + length > len(data):
                break
            payload = data[body_start:body_start + length]
            out.append(Record(cmd, page, length, payload, pos))
            pos = body_start + length
        return out

    def iter_scripts(self):
        """Yield (slot_index, code_bytes) for each script code region.

        `code_bytes` is trimmed of trailing zero padding but includes the final
        EXIT/END. Empty slots (all zero) are skipped.
        """
        for rec in self.records():
            body = rec.payload.rstrip(b"\x00")
            if not body:
                continue
            yield rec.page, body


def extract_script_code(path):
    """Convenience: return the first non-empty script code blob in a scripts
    backup (that's the one the device actually runs)."""
    sf = SayobakFile.load(path)
    for _slot, code in sf.iter_scripts():
        return code
    raise SayobakError("no non-empty script found in backup")
