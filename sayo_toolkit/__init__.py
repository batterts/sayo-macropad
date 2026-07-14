"""Local, offline toolkit for the SayoDevice on-device scripting VM (v3 bytecode).

No dependency on the vendor's hosted web tool. Pure-Python core (isa, assembler,
sayobak); the optional uploader (upload.py) needs `hid`/hidapi.
"""
from .assembler import assemble, disassemble, AsmError
from .sayobak import SayobakFile, extract_script_code, SayobakError

__all__ = [
    "assemble", "disassemble", "AsmError",
    "SayobakFile", "extract_script_code", "SayobakError",
]
