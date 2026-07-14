"""
SayoDevice on-device scripting VM — instruction set (v3 bytecode).

Transcribed from the vendor manual (script.md, section 3 "指令列表", the register
list in section 1.3, and the HID keycode tables in section 7).

Encoding rules (manual section 2):
  - opcode is always 1 byte
  - instruction length is variable, 1..6 bytes
  - operands are little-endian EXCEPT `label`, which the manual defines as an
    unsigned 16-bit BIG-endian absolute address ("无符号16位大端立即数")
  - operand byte widths: reg=1, u8/i8=1, u16/i16=2, u32/i32=4, rgb888=3, label=2

Register indices are the position of the name in the manual's register list.
This is INFERRED, but confirmed by two independent samples:
  - PRINT_REG R0  => 34 04            (R0  == index 4)
  - MOV R0 SYS_KBLED => 6e 04 14      (SYS_KBLED == index 20 == 0x14)
"""

# operand kind -> width in bytes
OPERAND_WIDTH = {
    "reg": 1,
    "u8": 1, "i8": 1,
    "u16": 2, "i16": 2,
    "u32": 4, "i32": 4,
    "rgb888": 3,
    "label": 2,   # big-endian, absolute PC
}

# mnemonic -> (opcode, total_length, [operand kinds])
# total_length is authoritative (from the manual); it must equal
# 1 + sum(OPERAND_WIDTH[o] for o in operands).
INSTRUCTIONS = {
    "END":               (0x00, 1, []),
    "NOP":               (0x01, 1, []),
    "JMP":               (0x02, 3, ["label"]),
    "SJMP":              (0x03, 2, ["i8"]),
    "AJMP":              (0x04, 2, ["u8"]),
    "SLEEP_X256":        (0x05, 2, ["u8"]),
    "SLEEP":             (0x06, 2, ["u8"]),
    "SLEEP_RAND_X256":   (0x07, 2, ["u8"]),
    "SLEEP_RAND":        (0x08, 2, ["u8"]),
    "SLEEP_X256_VAL":    (0x09, 2, ["reg"]),
    "SLEEP_VAL":         (0x0A, 2, ["reg"]),
    "SLEEP_RAND_X8_VAL": (0x0B, 2, ["reg"]),
    "SLEEP_RAND_VAL":    (0x0C, 2, ["reg"]),
    "SLEEP_U16":         (0x0D, 3, ["u16"]),
    "SLEEP_RAND_U16":    (0x0E, 3, ["u16"]),
    "PRESS_SK":          (0x10, 2, ["u8"]),
    "PRESS_GK":          (0x11, 2, ["u8"]),
    "PRESS_MK":          (0x12, 2, ["u8"]),
    "PRESS_MU":          (0x13, 2, ["u8"]),
    "PRESS_SK_VAL":      (0x14, 2, ["reg"]),
    "PRESS_GK_VAL":      (0x15, 2, ["reg"]),
    "PRESS_MK_VAL":      (0x16, 2, ["reg"]),
    "PRESS_MU_VAL":      (0x17, 2, ["reg"]),
    "RELEASE_SK":        (0x18, 2, ["u8"]),
    "RELEASE_GK":        (0x19, 2, ["u8"]),
    "RELEASE_MK":        (0x1A, 2, ["u8"]),
    "RELEASE_MU":        (0x1B, 2, ["u8"]),
    "RELEASE_SK_VAL":    (0x1C, 2, ["reg"]),
    "RELEASE_GK_VAL":    (0x1D, 2, ["reg"]),
    "RELEASE_MK_VAL":    (0x1E, 2, ["reg"]),
    "RELEASE_MU_VAL":    (0x1F, 2, ["reg"]),
    "UPDATE":            (0x20, 1, []),
    "MO_XYZ":            (0x21, 3, ["u8", "i8"]),
    "MO_XYZ_VAL":        (0x22, 3, ["u8", "reg"]),
    "GA_XYZ":            (0x23, 4, ["u8", "u16"]),
    "GA_XYZ_VAL":        (0x24, 3, ["u8", "reg"]),
    "TB_XY":             (0x25, 5, ["i16", "i16"]),
    "TB_XY_VAL":         (0x26, 3, ["reg", "reg"]),
    "DIAL_DATA":         (0x27, 2, ["u8"]),
    "DIAL_DATA_VAL":     (0x28, 2, ["reg"]),
    "KEY_TO_AXIS":       (0x29, 1, []),
    "PRESS_GAK":         (0x2C, 2, ["u8"]),
    "PRESS_GAK_VAL":     (0x2D, 2, ["reg"]),
    "RELEASE_GAK":       (0x2E, 2, ["u8"]),
    "RELEASE_GAK_VAL":   (0x2F, 2, ["reg"]),
    "C2K":               (0x30, 1, []),
    "U2K":               (0x31, 1, []),
    "C2K_RAND":          (0x32, 1, []),
    "U2K_REG":           (0x33, 1, []),
    "PRINT_REG":         (0x34, 2, ["reg"]),
    "JFA":               (0x40, 4, ["reg", "reg", "reg"]),
    "JFB":               (0x41, 4, ["reg", "reg", "reg"]),
    "JFG":               (0x42, 4, ["reg", "reg", "reg"]),
    "JFL":               (0x43, 4, ["reg", "reg", "reg"]),
    "JA":                (0x44, 5, ["reg", "reg", "label"]),
    "JB":                (0x45, 5, ["reg", "reg", "label"]),
    "JG":                (0x46, 5, ["reg", "reg", "label"]),
    "JL":                (0x47, 5, ["reg", "reg", "label"]),
    "JFC":               (0x48, 2, ["reg"]),
    "JFNC":              (0x49, 2, ["reg"]),
    "JFZ":               (0x4A, 3, ["reg", "reg"]),
    "JFNZ":              (0x4B, 3, ["reg", "reg"]),  # manual lists 1 operand but len=3; target reg like JFZ
    "DJFNZ":             (0x4C, 3, ["reg", "reg"]),
    "CJFNE":             (0x4D, 4, ["reg", "reg", "reg"]),
    "JC":                (0x4E, 3, ["label"]),
    "JNC":               (0x4F, 3, ["label"]),
    "JZ":                (0x50, 4, ["reg", "label"]),
    "JNZ":               (0x51, 4, ["reg", "label"]),
    "DJNZ":              (0x52, 4, ["reg", "label"]),
    "CJNE":              (0x53, 5, ["reg", "reg", "label"]),
    "CALL":              (0x54, 3, ["label"]),
    "RET":               (0x55, 1, []),
    "AND":               (0x56, 3, ["reg", "reg"]),
    "AND8":              (0x57, 3, ["reg", "u8"]),
    "ADD_A":             (0x58, 2, ["reg"]),
    "ADD8_A":            (0x59, 2, ["u8"]),
    "SUB_A":             (0x5A, 2, ["reg"]),
    "SUB8_A":            (0x5B, 2, ["u8"]),
    "OR_A":              (0x5C, 2, ["reg"]),
    "OR8_A":             (0x5D, 2, ["u8"]),
    "DEC":               (0x5E, 2, ["reg"]),
    "INC":               (0x5F, 2, ["reg"]),
    "MUL_A":             (0x60, 1, []),
    "DIV_A":             (0x61, 1, []),
    "XOR":               (0x62, 3, ["reg", "reg"]),
    "XOR8":              (0x63, 3, ["reg", "u8"]),
    "SHL":               (0x64, 3, ["reg", "reg"]),
    "SHL8":              (0x65, 3, ["reg", "u8"]),
    "SHR":               (0x66, 3, ["reg", "reg"]),
    "SHR8":              (0x67, 3, ["reg", "u8"]),
    "CLR":               (0x68, 2, ["reg"]),
    "NOT":               (0x69, 2, ["reg"]),
    "XCH":               (0x6A, 3, ["reg", "reg"]),
    "CMP":               (0x6B, 3, ["reg", "reg"]),
    "PUSH":              (0x6C, 2, ["reg"]),
    "POP":               (0x6D, 2, ["reg"]),
    "MOV":               (0x6E, 3, ["reg", "reg"]),
    "MOV8":              (0x6F, 3, ["reg", "u8"]),
    "MOV16":             (0x70, 4, ["reg", "u16"]),
    "MOV32":             (0x71, 6, ["reg", "u32"]),
    "ADD":               (0x72, 3, ["reg", "reg"]),
    "ADD8":              (0x73, 3, ["reg", "u8"]),
    "ADD16":             (0x74, 4, ["reg", "u16"]),
    "SUB":               (0x75, 3, ["reg", "reg"]),
    "SUB8":              (0x76, 3, ["reg", "u8"]),
    "SUB16":             (0x77, 4, ["reg", "u16"]),
    "OR":                (0x78, 3, ["reg", "reg"]),
    "OR8":               (0x79, 3, ["reg", "u8"]),
    "AND16":             (0x7A, 4, ["reg", "u16"]),
    "OR16":              (0x7B, 4, ["reg", "u16"]),
    "XOR16":             (0x7C, 4, ["reg", "u16"]),
    "ADD32":             (0x7D, 6, ["reg", "u32"]),
    "SUB32":             (0x7E, 6, ["reg", "u32"]),
    "AND32":             (0x7F, 6, ["reg", "u32"]),
    "OR32":              (0x80, 6, ["reg", "u32"]),
    "XOR32":             (0x81, 6, ["reg", "u32"]),
    "ADD_R":             (0x82, 4, ["reg", "reg", "reg"]),
    "SUB_R":             (0x83, 4, ["reg", "reg", "reg"]),
    "AND_R":             (0x84, 4, ["reg", "reg", "reg"]),
    "OR_R":              (0x85, 4, ["reg", "reg", "reg"]),
    "XOR_R":             (0x86, 4, ["reg", "reg", "reg"]),
    "MUL_R":             (0x87, 4, ["reg", "reg", "reg"]),
    "DIV_R":             (0x88, 4, ["reg", "reg", "reg"]),
    "MOD_R":             (0x89, 4, ["reg", "reg", "reg"]),
    "MOVSX8b":           (0x8A, 3, ["reg", "reg"]),
    "MOVSX16b":          (0x8B, 3, ["reg", "reg"]),
    "MOV8SX":            (0x8C, 3, ["reg", "u8"]),
    "MOV16SX":           (0x8D, 4, ["reg", "i16"]),
    "IMUL_A":            (0x8E, 1, []),
    "IMUL_R":            (0x8F, 4, ["reg", "reg", "reg"]),
    "LED_CTRL":          (0xE0, 2, ["u8"]),
    "LED_COL":           (0xE1, 4, ["rgb888"]),
    "START":             (0xE2, 2, ["u8"]),
    "STOP":              (0xE3, 2, ["u8"]),
    "SYCON":             (0xE8, 2, ["u8"]),
    "MALLOC":            (0xF0, 2, ["reg"]),
    "FREE":              (0xF1, 2, ["reg"]),
    "NEW_THREAD":        (0xF2, 4, ["u8", "reg", "reg"]),
    "WHILE_UPDATE":      (0xF4, 1, []),
    "JMP_TO_SCRIPT":     (0xF5, 2, ["u8"]),
    "MOV_PC2REG":        (0xF6, 2, ["reg"]),
    "VALUE_RELOAD":      (0xF7, 2, ["reg"]),
    "MODE_JOG":          (0xF8, 1, []),
    "WAIT_IF_RELEASE":   (0xF9, 1, []),
    "WAIT_IF_PRESS":     (0xFA, 1, []),
    "EXIT_IF_RELEAS":    (0xFB, 1, []),
    "EXIT_IF_PRESS":     (0xFC, 1, []),
    "EXIT_IF_ANYKEY":    (0xFD, 1, []),
    "RES":               (0xFE, 1, []),
    "EXIT":              (0xFF, 1, []),
}

# opcode -> (mnemonic, length, operands)
OPCODE_TABLE = {op: (mn, ln, ops) for mn, (op, ln, ops) in INSTRUCTIONS.items()}

# sanity: declared length must match operand widths
for _mn, (_op, _ln, _ops) in INSTRUCTIONS.items():
    _calc = 1 + sum(OPERAND_WIDTH[o] for o in _ops)
    assert _calc == _ln, f"{_mn}: declared len {_ln} != computed {_calc}"

# ---------------------------------------------------------------------------
# Register file. Index == position in the manual's register list (section 1.3).
# Entries whose name starts with '*' are indirect-addressing forms.
# ---------------------------------------------------------------------------
_REGISTER_ORDER = [
    "V0", "V1", "V2", "V3",
    "R0", "R1", "R2", "R3",
    "*DPTR", "DPTR", "KEY_IO",
    "*R0", "*R1", "*R2", "*R3",
    "ZERO", "A", "B",
    "SYS_TIME_MS", "SYS_TIME_S", "SYS_KBLED", "SYS_KEY_COUNT", "SYS_KEY_LAY",
    "SCRIPT_ADDR", "RANDOM", "SYS_BLE_NUM", "SYS_VOLUME",
    "SELECTED_LED", "SELECTED_LED_COL", "ALL_LED_COL", "CFG_ADDR", "HE_KEY_LV",
    "R4", "R5", "R6", "R7", "R8", "R9", "R10", "R11", "R12", "R13", "R14", "R15",
    "*R4", "*R5", "*R6", "*R7",
    "*R0_16b", "*R1_16b", "*R2_16b", "*R3_16b",
    "*R4_16b", "*R5_16b", "*R6_16b", "*R7_16b",
    "*R0_32b", "*R1_32b", "*R2_32b", "*R3_32b",
    "*R4_32b", "*R5_32b", "*R6_32b", "*R7_32b",
    # GL_0.. (global regs) follow; count is device-dependent (GL_SIZE, 4..64)
]
REG_NAME_TO_IDX = {name: i for i, name in enumerate(_REGISTER_ORDER)}
# Global registers are at a FIXED base of 128 (GL0=128, GL1=129, ...), per the
# vendor's parameter.json — NOT immediately after the per-thread file. Accept
# both GL_0 and GL0 spellings.
for _i in range(64):
    REG_NAME_TO_IDX[f"GL_{_i}"] = 128 + _i
    REG_NAME_TO_IDX[f"GL{_i}"] = 128 + _i
REG_IDX_TO_NAME = {i: n for n, i in REG_NAME_TO_IDX.items()}

# ---------------------------------------------------------------------------
# HID keycode symbol tables (manual section 7). Symbolic -> value.
# ---------------------------------------------------------------------------
HID_MODIFIER = {
    "hidkey_L_Ctrl": 0x01, "hidkey_L_Shift": 0x02, "hidkey_L_Alt": 0x04,
    "hidkey_L_Meta": 0x08, "hidkey_R_Ctrl": 0x10, "hidkey_R_Shift": 0x20,
    "hidkey_R_Alt": 0x40, "hidkey_R_Meta": 0x80,
}

# Normal keys: build A-Z, 0-9 plus the named specials from the manual.
HID_KEY = {}
for _i, _c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
    HID_KEY[f"hidkey_{_c}"] = 0x04 + _i
_DIGIT_NAMES = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]
for _i, _d in enumerate(_DIGIT_NAMES):
    HID_KEY[f"hidkey_{_d}"] = 0x1E + _i
HID_KEY.update({
    "hidkey_Enter": 0x28, "hidkey_Escape": 0x29, "hidkey_Backspace": 0x2A,
    "hidkey_Tab": 0x2B, "hidkey_Space": 0x2C, "hidkey_Minus": 0x2D,
    "hidkey_Equal": 0x2E, "hidkey_BracketLeft": 0x2F, "hidkey_BracketRight": 0x30,
    "hidkey_Backslash": 0x31, "hidkey_Semicolon": 0x33, "hidkey_Quote": 0x34,
    "hidkey_Backquote": 0x35, "hidkey_Comma": 0x36, "hidkey_Period": 0x37,
    "hidkey_Slash": 0x38, "hidkey_CapsLock": 0x39,
})
for _i in range(1, 13):
    HID_KEY[f"hidkey_F{_i}"] = 0x3A + (_i - 1)
HID_KEY.update({
    "hidkey_PrintScreen": 0x46, "hidkey_ScrollLock": 0x47, "hidkey_Pause": 0x48,
    "hidkey_Insert": 0x49, "hidkey_Home": 0x4A, "hidkey_PageUp": 0x4B,
    "hidkey_Delete": 0x4C, "hidkey_End": 0x4D, "hidkey_PageDown": 0x4E,
    "hidkey_ArrowRight": 0x4F, "hidkey_ArrowLeft": 0x50, "hidkey_ArrowDown": 0x51,
    "hidkey_ArrowUp": 0x52, "hidkey_NumLock": 0x53,
    "hidkey_AudioVolumeMute": 0x7F, "hidkey_AudioVolumeUp": 0x80,
    "hidkey_AudioVolumeDown": 0x81,
    "hidkey_ControlLeft": 0xE0, "hidkey_ShiftLeft": 0xE1, "hidkey_AltLeft": 0xE2,
    "hidkey_MetaLeft": 0xE3, "hidkey_ControlRight": 0xE4, "hidkey_ShiftRight": 0xE5,
    "hidkey_AltRight": 0xE6, "hidkey_MetaRight": 0xE7,
})

HID_MOUSE = {
    "hidmouse_0": 0x01, "hidmouse_1": 0x02, "hidmouse_2": 0x04,
    "hidmouse_3": 0x08, "hidmouse_4": 0x10,
}

HID_MEDIA = {
    "hidmedia_BrightnessUp": 1, "hidmedia_BrightnessDown": 2, "hidmedia_ToggleCmera": 3,
    "hidmedia_BeginScreenCapture": 4, "hidmedia_OpenGameBar": 5, "hidmedia_ScreenShot": 6,
    "hidmedia_BeginStreaming": 7, "hidmedia_Mute": 8, "hidmedia_Bass": 9,
    "hidmedia_VolumeUp": 10, "hidmedia_VolumeDown": 11, "hidmedia_PlayPause": 12,
    "hidmedia_Stop": 13, "hidmedia_PreviousTrack": 14, "hidmedia_NextTrack": 15,
    "hidmedia_BassUp": 16, "hidmedia_BassDown": 17, "hidmedia_TrebleUp": 18,
    "hidmedia_TrebleDown": 19, "hidmedia_MediaSelect": 20, "hidmedia_Mail": 21,
    "hidmedia_Calculator": 22, "hidmedia_Explorer": 23, "hidmedia_WWWSearch": 24,
    "hidmedia_WWWHome": 25, "hidmedia_WWWBack": 26, "hidmedia_WWWForward": 27,
    "hidmedia_WWWStop": 28, "hidmedia_WWWRefresh": 29, "hidmedia_WWWFavorites": 30,
}

# All symbolic constants the assembler will accept as immediate values.
SYMBOLS = {}
SYMBOLS.update(HID_MODIFIER)
SYMBOLS.update(HID_KEY)
SYMBOLS.update(HID_MOUSE)
SYMBOLS.update(HID_MEDIA)

# Reverse maps for the disassembler (value -> pretty name), per operand context.
HID_KEY_REV = {v: k for k, v in HID_KEY.items()}
HID_MODIFIER_REV = {v: k for k, v in HID_MODIFIER.items()}
HID_MEDIA_REV = {v: k for k, v in HID_MEDIA.items()}
HID_MOUSE_REV = {v: k for k, v in HID_MOUSE.items()}

# Which mnemonics take a HID symbol in their u8 operand, and of what flavor,
# so the disassembler can annotate them.
U8_HID_HINT = {
    "PRESS_GK": HID_KEY_REV, "RELEASE_GK": HID_KEY_REV,
    "PRESS_SK": HID_MODIFIER_REV, "RELEASE_SK": HID_MODIFIER_REV,
    "PRESS_MK": HID_MOUSE_REV, "RELEASE_MK": HID_MOUSE_REV,
    "PRESS_MU": HID_MEDIA_REV, "RELEASE_MU": HID_MEDIA_REV,
}
