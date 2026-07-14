"""
Two-way translator for SayoDevice v3 script bytecode.

assemble(text)   -> bytes     (source .v3 assembly -> raw opcodes)
disassemble(code)-> str       (raw opcodes -> annotated assembly)

The assembly syntax matches the vendor manual's examples:
  - one instruction per line: MNEMONIC [op1] [op2] [op3]
  - `;` starts a comment
  - a bare `name:` defines a label (absolute PC address of the next byte)
  - operands may be: a register name (R0, SYS_KBLED, *R1, ...), a decimal or
    0x-hex integer, a char literal 'A', or a symbolic HID name (hidkey_K, ...)
  - `label` operands reference a label name (encoded big-endian) or an integer
"""

from .isa import (
    INSTRUCTIONS, OPCODE_TABLE, OPERAND_WIDTH,
    REG_NAME_TO_IDX, REG_IDX_TO_NAME, SYMBOLS, U8_HID_HINT,
)


class AsmError(Exception):
    pass


# ---------------------------------------------------------------------------
# operand encoding helpers
# ---------------------------------------------------------------------------

def _parse_int(tok):
    t = tok.strip()
    if len(t) == 3 and t[0] == "'" and t[2] == "'":
        return ord(t[1])
    if t in SYMBOLS:
        return SYMBOLS[t]
    try:
        return int(t, 0)
    except ValueError:
        raise AsmError(f"not an integer/known symbol: {tok!r}")


def _enc_reg(tok):
    t = tok.strip()
    if t in REG_NAME_TO_IDX:
        return bytes([REG_NAME_TO_IDX[t]])
    # allow a raw index too
    n = _parse_int(t)
    if not 0 <= n <= 0xFF:
        raise AsmError(f"register index out of range: {tok!r}")
    return bytes([n])


def _enc_uint(val, width, signed):
    lo = -(1 << (8 * width - 1)) if signed else 0
    hi = (1 << (8 * width - 1)) - 1 if signed else (1 << (8 * width)) - 1
    if not lo <= val <= hi:
        raise AsmError(f"value {val} out of range for {'i' if signed else 'u'}{8*width}")
    return int(val).to_bytes(width, "little", signed=signed)


def _encode_operand(kind, tok, labels):
    if kind == "reg":
        return _enc_reg(tok)
    if kind == "rgb888":
        return _enc_uint(_parse_int(tok) & 0xFFFFFF, 3, False)
    if kind == "label":
        if tok in labels:
            addr = labels[tok]
        else:
            addr = _parse_int(tok)
        if not 0 <= addr <= 0xFFFF:
            raise AsmError(f"label address out of range: {tok!r}")
        return addr.to_bytes(2, "big")          # labels are BIG-endian
    signed = kind[0] == "i"
    width = OPERAND_WIDTH[kind]
    return _enc_uint(_parse_int(tok), width, signed)


# ---------------------------------------------------------------------------
# tokenizer
# ---------------------------------------------------------------------------

def _tokenize(line):
    line = line.split(";", 1)[0].strip()
    if not line:
        return None
    # label definition:  name:
    if line.endswith(":") and len(line.split()) == 1:
        return ("label", line[:-1])
    parts = line.replace(",", " ").split()
    return ("insn", parts[0].upper(), parts[1:])


# ---------------------------------------------------------------------------
# assembler (two-pass)
# ---------------------------------------------------------------------------

def assemble(text):
    # Pass 1: compute the address of each label.
    pc = 0
    labels = {}
    program = []          # list of (mnemonic, operands, source_lineno)
    for lineno, raw in enumerate(text.splitlines(), 1):
        tok = _tokenize(raw)
        if tok is None:
            continue
        if tok[0] == "label":
            if tok[1] in labels:
                raise AsmError(f"line {lineno}: duplicate label {tok[1]!r}")
            labels[tok[1]] = pc
            continue
        _, mnemonic, operands = tok
        if mnemonic not in INSTRUCTIONS:
            raise AsmError(f"line {lineno}: unknown mnemonic {mnemonic!r}")
        _op, length, kinds = INSTRUCTIONS[mnemonic]
        if len(operands) != len(kinds):
            raise AsmError(
                f"line {lineno}: {mnemonic} takes {len(kinds)} operand(s), "
                f"got {len(operands)}")
        program.append((mnemonic, operands, lineno))
        pc += length

    # Pass 2: emit bytes.
    out = bytearray()
    for mnemonic, operands, lineno in program:
        opcode, length, kinds = INSTRUCTIONS[mnemonic]
        out.append(opcode)
        for kind, tok in zip(kinds, operands):
            try:
                out += _encode_operand(kind, tok, labels)
            except AsmError as e:
                raise AsmError(f"line {lineno}: {mnemonic} {tok!r}: {e}")
    return bytes(out)


# ---------------------------------------------------------------------------
# disassembler
# ---------------------------------------------------------------------------

def _pretty_reg(v):
    return REG_IDX_TO_NAME.get(v, f"r{v}")


def _decode_operand(kind, raw, mnemonic):
    if kind == "reg":
        return _pretty_reg(raw[0]), None
    if kind == "label":
        return f"0x{int.from_bytes(raw, 'big'):04X}", None
    if kind == "rgb888":
        return f"0x{int.from_bytes(raw, 'little'):06X}", None
    signed = kind[0] == "i"
    val = int.from_bytes(raw, "little", signed=signed)
    hint = None
    if kind == "u8" and mnemonic in U8_HID_HINT:
        hint = U8_HID_HINT[mnemonic].get(val)
    return str(val), hint


def disassemble(code, base=0, show_addr=True, show_bytes=True):
    """Return annotated assembly text. Unknown/oversized opcodes -> `DB 0xNN`."""
    lines = []
    i = 0
    n = len(code)
    while i < n:
        addr = base + i
        opcode = code[i]
        entry = OPCODE_TABLE.get(opcode)
        if entry is None:
            lines.append(_fmt(addr, code[i:i+1], f"DB 0x{opcode:02X}",
                              "; <undefined opcode — VM would abort thread>",
                              show_addr, show_bytes))
            i += 1
            continue
        mnemonic, length, kinds = entry
        if i + length > n:
            lines.append(_fmt(addr, code[i:], f"DB 0x{opcode:02X}",
                              f"; <truncated {mnemonic}: needs {length} bytes, "
                              f"{n - i} left>", show_addr, show_bytes))
            break
        raw = code[i:i + length]
        pos = i + 1
        args, notes = [], []
        for kind in kinds:
            w = OPERAND_WIDTH[kind]
            text, hint = _decode_operand(kind, code[pos:pos + w], mnemonic)
            args.append(text)
            if hint:
                notes.append(hint)
            pos += w
        asm = mnemonic + ("  " + " ".join(args) if args else "")
        note = ("; " + ", ".join(notes)) if notes else ""
        lines.append(_fmt(addr, raw, asm, note, show_addr, show_bytes))
        i += length
    return "\n".join(lines)


def _fmt(addr, raw, asm, note, show_addr, show_bytes):
    prefix = ""
    if show_addr:
        prefix += f"{addr:04X}:  "
    if show_bytes:
        prefix += f"{raw.hex():<14} "
    return f"{prefix}{asm}" + (f"    {note}" if note else "")
