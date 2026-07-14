#!/usr/bin/env python3
"""
Generate modes.v3 — the app-aware macropad script.

The daemon sets the current mode in lighting zone 1 (cmd 16). This script, on any
button press, reads that mode via LED_CTRL 1 + SELECTED_LED_COL, then branches to
the right keystroke for (mode, button). Buttons: V0 0=Left 1=Mid 2=Right 3=knob
press 4=knob CCW 5=knob CW.  Edit MODES below to change any mapping, then:
    python3 gen_modes.py && python3 sayoc.py asm modes.v3 -o modes.bin
"""
K = {  # HID key codes
    'ESC':0x29,'Q':0x14,'W':0x1A,'K':0x0E,'J':0x0D,'L':0x0F,'F':0x09,'R':0x15,
    'T':0x17,'B':0x05,'N':0x11,'P':0x13,'ENTER':0x28,'SEMI':0x33,'TAB':0x2B,
    '2':0x1F,'UP':0x52,'DOWN':0x51,'LBRK':0x2F,'RBRK':0x30,
    'F2':0x3B,'F7':0x40,'F8':0x41,'F9':0x42,
    'M':0x10,'O':0x12,'H':0x0B,'E':0x08,   # for MS Teams shortcuts
    'D':0x07,                              # for iTerm split
}
MOD = {'CTRL':0x01,'SHIFT':0x02,'ALT':0x04,'CMD':0x08}
MU  = {'PLAY':12,'NEXT':15,'PREV':14,'VUP':10,'VDOWN':11,'MUTE':8}

def tap(k):        return [f'PRESS_GK {K[k]}','SLEEP 12',f'RELEASE_GK {K[k]}','SLEEP 12']
def media(m):      return [f'PRESS_MU {MU[m]}','SLEEP 12',f'RELEASE_MU {MU[m]}','SLEEP 12']
def combo(mods,k):
    mask=0
    for m in mods: mask|=MOD[m]
    return [f'PRESS_SK {mask}','SLEEP 12',f'PRESS_GK {K[k]}','SLEEP 12',
            f'RELEASE_GK {K[k]}','SLEEP 12',f'RELEASE_SK {mask}','SLEEP 12']
def s(*parts):
    out=[]
    for p in parts: out+=p
    return out

# --- ASCII -> keystroke typing (for the "type the install command" macro) ---
# HID codes; (shift, code). Covers lowercase + the specials in the install command.
def _charmap():
    m = {}
    for i in range(26):
        m[chr(ord('a') + i)] = (False, 0x04 + i)          # a..z
        m[chr(ord('A') + i)] = (True,  0x04 + i)          # A..Z (shift)
    for i, d in enumerate("123456789"):
        m[d] = (False, 0x1E + i)
    m['0'] = (False, 0x27)
    m.update({
        ' ': (False, 0x2C), '-': (False, 0x2D), '.': (False, 0x37),
        '/': (False, 0x38), ':': (True, 0x33),  '~': (True, 0x35),
        '&': (True, 0x24),  '_': (True, 0x2D),  '=': (False, 0x2E),
    })
    return m
_CHARS = _charmap()

def typestr(text):
    """Emit assembly that types `text` as HID keystrokes (with shift where needed)."""
    out = []
    for ch in text:
        if ch not in _CHARS:
            raise ValueError(f"no keymap for {ch!r}")
        shift, code = _CHARS[ch]
        if shift: out += ['PRESS_SK 2']
        out += [f'PRESS_GK {code}', 'SLEEP 6', f'RELEASE_GK {code}']
        if shift: out += ['RELEASE_SK 2']
        out += ['SLEEP 6']
    return out

# The plug-and-play bootstrap the knob long-press types (no trailing Enter — you
# review, then press Enter). Clones the public runtime repo and runs setup.sh.
INSTALL_CMD = "git clone https://github.com/batterts/sayo-macropad.git && cd sayo-macropad && ./setup.sh"

def knob_install_longpress():
    """Default-mode knob: quick press = Mute; hold ~1.5s = type the install command.
    KEY_IO reads the knob's own state (0=held). Poll ~150x10ms; early release=short."""
    return (['MOV16 A 150',
             'lp_wait:',
             'SLEEP 10',
             'JNZ KEY_IO lp_short',        # released early -> quick press
             'DJNZ A lp_wait',
             '; --- held long: type the install command ---']
            + typestr(INSTALL_CMD)
            + ['JMP lp_end',
               'lp_short:'] + media('MUTE') + ['lp_end:'])

# mode -> {V0(button) -> keystroke sequence}
MODES = {
 0: {  # default / no matched app: system media transport
   0: media('PREV'), 1: media('PLAY'), 2: media('NEXT'),
   3: knob_install_longpress(),   # quick=Mute, hold 1.5s=type install command
   4: media('VDOWN'), 5: media('VUP'),
 },
 1: {  # MacVim
   0: s(tap('ESC'),tap('Q'),tap('Q')),                                  # record <ESC>qq
   1: s(tap('ESC'),combo(['SHIFT'],'2'),tap('Q')),                      # play <ESC>@q
   2: s(tap('ESC'),combo(['SHIFT'],'SEMI'),tap('W'),tap('ENTER')),      # save <ESC>:w
   3: s(tap('ESC'),tap('Q')),                                           # stop rec <ESC>q
   4: s(tap('ESC'),combo(['SHIFT'],'SEMI'),tap('B'),tap('P'),tap('ENTER')), # :bp
   5: s(tap('ESC'),combo(['SHIFT'],'SEMI'),tap('B'),tap('N'),tap('ENTER')), # :bn
 },
 2: {  # browser (Safari/Chrome)
   0: combo(['CMD'],'LBRK'),           # back
   1: combo(['CMD'],'T'),              # new tab
   2: combo(['CMD'],'RBRK'),           # forward
   3: combo(['CMD'],'R'),              # reload
   4: combo(['CTRL','SHIFT'],'TAB'),   # prev tab
   5: combo(['CTRL'],'TAB'),           # next tab
 },
 3: {  # YouTube (browser on youtube.com)
   0: tap('J'),    # rewind 10s
   1: tap('K'),    # play/pause
   2: tap('L'),    # ffwd 10s
   3: tap('F'),    # fullscreen
   4: tap('DOWN'), # volume down
   5: tap('UP'),   # volume up
 },
 4: {  # IntelliJ debugger
   0: tap('F7'),               # step into
   1: tap('F8'),               # step over
   2: tap('F9'),               # resume
   3: combo(['CMD'],'F8'),     # toggle breakpoint
   4: combo(['CMD'],'F2'),     # stop
   5: combo(['SHIFT'],'F8'),   # step out
 },
 5: {  # MS Teams (macOS shortcuts)
   0: combo(['CMD','SHIFT'],'O'),   # toggle camera
   1: combo(['CMD','SHIFT'],'K'),   # raise / lower hand
   2: combo(['CMD','SHIFT'],'H'),   # leave call
   3: combo(['CMD','SHIFT'],'M'),   # knob push = mute / unmute mic
   4: media('VDOWN'),               # volume down
   5: media('VUP'),                 # volume up
 },
 6: {  # iTerm2 terminal
   0: combo(['CMD'],'T'),               # new tab
   1: combo(['CMD'],'D'),               # split pane (vertical)
   2: combo(['CMD'],'W'),               # close tab / pane
   3: combo(['CMD'],'K'),               # knob push = clear screen
   4: combo(['CMD','SHIFT'],'LBRK'),    # prev tab
   5: combo(['CMD','SHIFT'],'RBRK'),    # next tab
 },
}

def gen():
    L=['; AUTO-GENERATED by gen_modes.py — app-aware macropad',
       'MODE_JOG',
       'LED_CTRL 1','MOV R3 SELECTED_LED_COL','AND8 R3 255',  '; R3 = mode']
    # mode dispatch
    modes=sorted(MODES)
    for i,m in enumerate(modes):
        L+=[f'MOV8 R1 {m}', f'CJNE R3 R1 mchk_{i}', f'JMP mode_{m}', f'mchk_{i}:']
    L+=['JMP done']  # unknown mode
    # per-mode V0 dispatch
    for m in modes:
        L+=[f'mode_{m}:']
        btns=sorted(MODES[m])
        for j,v in enumerate(btns):
            L+=[f'MOV8 R1 {v}', f'CJNE V0 R1 vchk_{m}_{j}', f'JMP b_{m}_{v}', f'vchk_{m}_{j}:']
        L+=['JMP done']
    # button sequences
    for m in modes:
        for v in sorted(MODES[m]):
            L+=[f'b_{m}_{v}:'] + MODES[m][v] + ['JMP done']
    L+=['done:','EXIT']
    return '\n'.join(L)+'\n'

if __name__=='__main__':
    open('modes.v3','w').write(gen())
    print('wrote modes.v3')
