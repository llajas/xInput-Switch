#!/usr/bin/env python3
"""
XInput-to-serial bridge  –  HOME = BACK + START combo
─────────────────────────────────────────────────────
• Windows-only, 100 Hz stream, survives disconnects
• Pauses (sends neutral) while a given window lacks focus
• Interactive prompts for COM port and controller slot unless --auto
"""

import argparse, ctypes, sys, time
import serial, serial.tools.list_ports
try:
    import win32gui           # window focus gating
except ImportError:
    win32gui = None

# ────────── Switch protocol helpers ──────────
CMD1, CMD2, CMD_ST = 0x33, 0xCC, 0xFF
RSP_ST, RSP1, RSP_OK = 0xFF, 0xCC, 0x33
BAUD_DEF, SEND, RETRY = 1_000_000, 0.01, 0.50          # 100 Hz

def crc8(data: bytes) -> int:
    c = 0
    for b in data:
        c ^= b
        for _ in range(8):
            c = ((c << 1) ^ 0x07) & 0xFF if c & 0x80 else (c << 1) & 0xFF
    return c

class UART:
    def __init__(self, port: str, baud: int):
        self.h = serial.Serial(port, baudrate=baud, timeout=0.05)
    def write(self, payload: bytes):
        self.h.write(payload + bytes([crc8(payload)]))
    def sync(self) -> bool:
        self.h.write(bytes([CMD_ST]) * 9)
        start = time.time()
        while time.time() - start < 1:
            if self.h.in_waiting and self.h.read(1)[0] == RSP_ST:
                self.h.write(bytes([CMD1]))
                if self.h.read(1)[0] == RSP1:
                    self.h.write(bytes([CMD2]))
                    return self.h.read(1)[0] == RSP_OK
        return False
    def close(self):
        self.h.close()

class Packet:
    def __init__(self, b, d, lx, ly, rx, ry):
        self.b, self.d, self.lx, self.ly, self.rx, self.ry = b, d, lx, ly, rx, ry
    def pack(self):
        norm = lambda v: int((v + 1) / 2 * 255) & 0xFF
        a = [(self.b >> 8) & 0xFF, self.b & 0xFF, self.d & 0xFF,
             norm(self.lx), norm(self.ly), norm(self.rx), norm(self.ry), 0]
        for i in (3, 4, 5, 6):
            if abs(a[i] - 0x80) < 10:
                a[i] = 0x80
        return bytes(a)

# ────────── XInput ctypes wrapper ──────────
for dll in ("xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll"):
    try:
        _x = ctypes.windll.LoadLibrary(dll); break
    except OSError:
        _x = None
if _x is None:
    sys.exit("No XInput DLL found")

class _GP(ctypes.Structure):
    _fields_ = [("wButtons", ctypes.c_ushort),
                ("bLT", ctypes.c_ubyte), ("bRT", ctypes.c_ubyte),
                ("sLX", ctypes.c_short), ("sLY", ctypes.c_short),
                ("sRX", ctypes.c_short), ("sRY", ctypes.c_short)]
class _ST(ctypes.Structure):
    _fields_ = [("dwPacketNumber", ctypes.c_uint), ("Gamepad", _GP)]
_x.XInputGetState.argtypes = [ctypes.c_uint, ctypes.POINTER(_ST)]

BTN_MASKS = [
    0x1000, 0x2000, 0x4000, 0x8000,   # A B X Y
    0x0100, 0x0200,                   # LB RB
    0x0020, 0x0010,                   # BACK / SELECT, START
    0x0400, 0x0040, 0x0080            # GUIDE, L-stick, R-stick
]

class Pad:
    def __init__(self, slot: int):
        self.slot = slot
        self.st = _ST()
    def ok(self):       return _x.XInputGetState(self.slot, ctypes.byref(self.st)) == 0
    def btn(self, i):   return bool(self.st.Gamepad.wButtons & BTN_MASKS[i])
    def axis(self, i):
        g = self.st.Gamepad
        return [g.sLX/32767, g.sLY/32767, g.bLT/255,
                g.sRX/32767, g.sRY/32767, g.bRT/255][i]
    def hat(self):
        w = self.st.Gamepad.wButtons
        return ((1 if w & 0x0008 else 0) + (-1 if w & 0x0004 else 0),
                (1 if w & 0x0001 else 0) + (-1 if w & 0x0002 else 0))
    def raw(self):      return self.st.Gamepad.wButtons

BTN_MAP = {
    0: 1 << 1,   # south (Xbox A)  -> Switch A
    1: 1 << 2,   # east  (Xbox B)  -> Switch B
    2: 1 << 0,   # west  (Xbox X)  -> Switch Y
    3: 1 << 3,   # north (Xbox Y)  -> Switch X
    4: 1 << 4,   # LB -> L
    5: 1 << 5,   # RB -> R
    6: 1 << 8,   # BACK -> MINUS
    7: 1 << 9,   # START -> PLUS
    9: 1 << 10,  # L-stick click
    10: 1 << 11  # R-stick click
}
HAT_MAP = {(0,1):0,(1,1):1,(1,0):2,(1,-1):3,(0,-1):4,
           (-1,-1):5,(-1,0):6,(-1,1):7,(0,0):8}

def build_packet(p: Pad):
    b = 0
    for idx, mask in BTN_MAP.items():
        if p.btn(idx): b |= mask
    if p.btn(6) and p.btn(7):          # BACK + START => HOME
        b |= 1 << 12
    if p.axis(2) > 0.5: b |= 1 << 6    # ZL
    if p.axis(5) > 0.5: b |= 1 << 7    # ZR
    hx, hy = p.hat()
    return Packet(b, HAT_MAP[(hx, hy)],
                  p.axis(0), p.axis(1),
                  p.axis(3), p.axis(4)), b

# ────────── selection helpers ──────────
def list_ports():
    return [p.device for p in serial.tools.list_ports.comports()]

def choose_port():
    ports = list_ports()
    if not ports:
        return None
    print("Available COM ports:")
    for i, p in enumerate(ports):
        print(f"  {i}: {p}")
    idx = input("Pick port index: ")
    try:
        return ports[int(idx)]
    except (ValueError, IndexError):
        return None

def scan_first_pad():
    for s in range(4):
        pad = Pad(s)
        if pad.ok():
            return pad
    return None

def choose_pad_interactive():
    found = [s for s in range(4) if Pad(s).ok()]
    if not found:
        print("No controllers detected.")
        return None
    print("Available controllers:")
    for s in found:
        print(f"  {s}: connected")
    idx = input("Pick controller slot (0-3): ")
    try:
        slot = int(idx)
        pad = Pad(slot)
        return pad if pad.ok() else None
    except ValueError:
        return None

def focus_ok(title: str):
    if win32gui is None:
        return True
    return title.lower() in win32gui.GetWindowText(
        win32gui.GetForegroundWindow()).lower()

# ────────── main ──────────
def main():
    pa = argparse.ArgumentParser()
    pa.add_argument("--port"); pa.add_argument("--baud", type=int, default=BAUD_DEF)
    pa.add_argument("--controller", type=int)
    pa.add_argument("--window"); pa.add_argument("--auto", action="store_true")
    pa.add_argument("--debug", action="store_true")
    args = pa.parse_args()

    if args.window and win32gui is None:
        sys.exit("pywin32 required for --window")

    # pick COM port
    port = args.port
    if not port and not args.auto:
        port = choose_port()
    if not port and args.auto:
        ports = list_ports()
        port = ports[0] if ports else None
    if port is None:
        sys.exit("No serial port selected")

    # pick controller
    pad = None
    if args.controller is not None:
        maybe = Pad(args.controller)
        pad = maybe if maybe.ok() else None
    elif args.auto:
        pad = scan_first_pad()
    else:
        pad = choose_pad_interactive()
    if pad is None:
        sys.exit("No controller selected / found")

    ser = UART(port, args.baud)
    if not ser.sync():
        sys.exit("MCU sync failed")
    if args.debug:
        print(f"Using COM {port} @ {args.baud} baud")
        print(f"Using controller slot {pad.slot}")

    neutral = Packet(0, 8, 0, 0, 0, 0)
    was_focused = True
    try:
        while True:
            # controller still present?
            if not pad.ok():
                ser.write(neutral.pack())
                if args.debug:
                    print("Pad lost – neutral")
                time.sleep(RETRY)
                pad = scan_first_pad() if args.auto else choose_pad_interactive()
                if pad and args.debug:
                    print(f"Controller reconnected on slot {pad.slot}")
                continue

            # window focus check
            in_focus = (not args.window) or focus_ok(args.window)
            if not in_focus:
                if was_focused and args.debug:
                    print("Window inactive – neutral")
                ser.write(neutral.pack())
                was_focused = False
                time.sleep(SEND)
                continue
            if not was_focused and args.debug:
                print("Window active – streaming")
            was_focused = True

            pkt, bits = build_packet(pad)
            ser.write(pkt.pack())
            if args.debug:
                print(f"buttons=0x{bits:04X} raw=0x{pad.raw():04X} pkt={pkt.pack().hex()}")
            time.sleep(SEND)
    except KeyboardInterrupt:
        pass
    finally:
        ser.close()

if __name__ == "__main__":
    main()
