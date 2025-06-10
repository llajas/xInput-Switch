#!/usr/bin/env python3
"""
XInput-to-serial bridge  –  HOME = BACK + START combo
─────────────────────────────────────────────────────
• Windows-only, 100 Hz stream, survives disconnects
• Pauses (sends neutral) while a given window lacks focus
• Interactive prompts for COM port and controller slot unless --auto
• Supports Keyboard+Mouse (FPS layout):
    - WASD → Left Stick
    - SPACE → Jump (Switch A)
    - CTRL → Crouch (Switch B)
    - R → Reload (Switch Y)
    - E → Interact (Switch X)
    - Q → Swap Weapon (Switch L)
    - F → Melee (Switch R)
    - TAB → Map/Menu (Switch MINUS)
    - ENTER → Start/Pause (Switch PLUS)
    - V → Lean Left (L-Stick click)
    - X → Lean Right (R-Stick click)
    - H → HOME
    - C → CAPTURE
    - Mouse movement → Right Stick (continuous, recenters each frame)
"""

import argparse, ctypes, sys, time
import serial, serial.tools.list_ports

try:
    import hid  # optional HIDAPI support
except ImportError:  # pragma: no cover - optional dependency
    hid = None

try:
    import win32gui
except ImportError:
    win32gui = None
try:
    import keyboard  # pip install keyboard
except ImportError:
    keyboard = None
try:
    import mouse     # pip install mouse
except ImportError:
    mouse = None

from ctypes import wintypes
user32 = ctypes.windll.user32

# ───────── protocol helpers ─────────
CMD1, CMD2, CMD_ST = 0x33, 0xCC, 0xFF
RSP_ST, RSP1, RSP_OK = 0xFF, 0xCC, 0x33
BAUD_DEF, SEND, RETRY = 1_000_000, 0.01, 0.50

def crc8(data: bytes) -> int:
    c = 0
    for b in data:
        c ^= b
        for _ in range(8):
            c = ((c << 1) ^ 0x07) & 0xFF if c & 0x80 else (c << 1) & 0xFF
    return c

class UART:
    def __init__(self, port: str):
        self.h = serial.Serial(port, baudrate=BAUD_DEF, timeout=0.05)
    def write(self, p: bytes):
        self.h.write(p + bytes([crc8(p)]))
    def sync(self) -> bool:
        self.h.write(bytes([CMD_ST]) * 9)
        t0 = time.time()
        while time.time() - t0 < 1:
            if self.h.in_waiting and self.h.read(1)[0] == RSP_ST:
                self.h.write(bytes([CMD1]))
                if self.h.read(1)[0] == RSP1:
                    self.h.write(bytes([CMD2]))
                    return self.h.read(1)[0] == RSP_OK
        return False
    def close(self):
        self.h.close()

class HIDUART:
    """Serial protocol over HID using hidapi."""

    def __init__(self, path: str):
        if hid is None:
            raise RuntimeError("hidapi library required for HID mode")
        self.h = hid.Device(path=path)
        self.h.set_nonblocking(True)

    def write(self, p: bytes):
        self.h.write(p + bytes([crc8(p)]))

    def _read_byte(self, timeout=0.05):
        t0 = time.time()
        while time.time() - t0 < timeout:
            data = self.h.read(1)
            if data:
                return data[0]
        return None

    def sync(self) -> bool:
        self.h.write(bytes([CMD_ST]) * 9)
        t0 = time.time()
        while time.time() - t0 < 1:
            b = self._read_byte()
            if b == RSP_ST:
                self.h.write(bytes([CMD1]))
                if self._read_byte() == RSP1:
                    self.h.write(bytes([CMD2]))
                    return self._read_byte() == RSP_OK
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

# ───────── XInput backend ─────────
for dll in ("xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll"):
    try:
        _x = ctypes.windll.LoadLibrary(dll)
        break
    except OSError:
        _x = None

class _GP(ctypes.Structure):
    _fields_ = [
        ("wButtons", ctypes.c_ushort),
        ("bLT", ctypes.c_ubyte), ("bRT", ctypes.c_ubyte),
        ("sLX", ctypes.c_short), ("sLY", ctypes.c_short),
        ("sRX", ctypes.c_short), ("sRY", ctypes.c_short),
    ]
class _ST(ctypes.Structure):
    _fields_ = [("dwPacketNumber", ctypes.c_uint), ("Gamepad", _GP)]
if _x is not None:
    _x.XInputGetState.argtypes = [ctypes.c_uint, ctypes.POINTER(_ST)]
BTN_MASKS = [0x1000,0x2000,0x4000,0x8000, 0x0100,0x0200, 0x0020,0x0010, 0x0400,0x0040,0x0080]

class PadX:
    def __init__(self, slot: int): self.slot, self.st = slot, _ST()
    def ok(self): return _x and _x.XInputGetState(self.slot, ctypes.byref(self.st)) == 0
    def btn(self,i): return bool(self.st.Gamepad.wButtons & BTN_MASKS[i])
    def axis(self,i):
        g=self.st.Gamepad
        return [g.sLX/32767, g.sLY/32767, g.bLT/255,
                g.sRX/32767, g.sRY/32767, g.bRT/255][i]
    def hat(self):
        w=self.st.Gamepad.wButtons
        return ((1 if w&0x0008 else 0)+(-1 if w&0x0004 else 0),
                (1 if w&0x0001 else 0)+(-1 if w&0x0002 else 0))
    def raw(self): return self.st.Gamepad.wButtons

# ───────── Keyboard+Mouse backend (FPS layout with recenter) ─────────
KEY_MAPPING = {0:'ctrl',1:'space',2:'r',3:'e',4:'q',5:'f',6:'tab',7:'enter',9:'v',10:'x'}

class PadK:
    SENS=30
    def __init__(self, center=None):
        if keyboard is None: raise RuntimeError("keyboard library required")
        self.prev_x=0; self.prev_y=0
        self.center = center
        if mouse:
            # move initially to center
            user32.SetCursorPos(center[0], center[1])
            self.prev_x, self.prev_y = center
    def ok(self): return True
    def btn(self,i): key=KEY_MAPPING.get(i); return keyboard.is_pressed(key) if key else False
    def axis(self,i):
        # left stick via WASD
        if i==0:
            return 1.0 if keyboard.is_pressed('d') else (-1.0 if keyboard.is_pressed('a') else 0.0)
        if i==1:
            return 1.0 if keyboard.is_pressed('w') else (-1.0 if keyboard.is_pressed('s') else 0.0)
        # right stick via mouse deltas
        if mouse and self.center:
            mx,my = mouse.get_position()
            dx = mx - self.prev_x
            dy = my - self.prev_y
            # recenter immediately
            user32.SetCursorPos(self.center[0], self.center[1])
            self.prev_x, self.prev_y = self.center
            if i==3:
                return max(-1, min(1, dx/self.SENS))
            if i==4:
                return max(-1, min(1, -dy/self.SENS))
        return 0.0
    def hat(self): return (0,0)
    def raw(self): return 0

BTN_MAP={0:1<<1,1:1<<2,2:1<<0,3:1<<3,4:1<<4,5:1<<5,6:1<<8,7:1<<9,9:1<<10,10:1<<11}
HAT_MAP={(0,1):0,(1,1):1,(1,0):2,(1,-1):3,(0,-1):4,(-1,-1):5,(-1,0):6,(-1,1):7,(0,0):8}

def build_packet(p):
    b=0
    for i,m in BTN_MAP.items():
        if p.btn(i): b|=m
    if keyboard and keyboard.is_pressed('h'): b|=1<<12
    if keyboard and keyboard.is_pressed('c'): b|=1<<13
    if isinstance(p,PadX) and p.btn(6) and p.btn(7): b|=1<<12
    if isinstance(p,PadX):
        if p.axis(2)>0.5: b|=1<<6
        if p.axis(5)>0.5: b|=1<<7
    else:
        if keyboard and keyboard.is_pressed('shift'): b|=1<<6
        if keyboard and keyboard.is_pressed('ctrl'):  b|=1<<7
    hx,hy=p.hat()
    return Packet(b,HAT_MAP[(hx,hy)],p.axis(0),p.axis(1),p.axis(3),p.axis(4)), b

def list_ports():
    """Return available serial or HIDAPI ports."""
    ports = [p.device for p in serial.tools.list_ports.comports()]
    if hid is not None:
        try:
            for d in hid.enumerate():
                path = d.get('path')
                if isinstance(path, bytes):
                    path = path.decode(errors='ignore')
                ports.append(f"hid:{path}")
        except Exception:
            pass
    return ports
def focus_ok(title:str):
    if win32gui is None: return True
    return title.lower() in win32gui.GetWindowText(win32gui.GetForegroundWindow()).lower()

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--keyboard",action="store_true")
    ap.add_argument("--port")
    ap.add_argument("--controller",type=int)
    ap.add_argument("--window")
    ap.add_argument("--auto",action="store_true")
    ap.add_argument("--debug",action="store_true")
    args=ap.parse_args()

    center=None
    if args.keyboard and args.window and win32gui:
        hwnd=win32gui.FindWindow(None,args.window)
        l,t,r,b=win32gui.GetWindowRect(hwnd)
        cx,cy=(l+r)//2,(t+b)//2
        center=(cx,cy)

    port=args.port
    if not port and not args.auto:
        ports=list_ports(); port=ports[0] if ports else None
    if not port and args.auto:
        ports=list_ports(); port=ports[0] if ports else None
    if not port: sys.exit("No serial port selected")

    pad = PadK(center) if args.keyboard else PadX(args.controller if args.controller is not None else 0)
    if not pad.ok(): sys.exit("Controller not connected")

    ser = HIDUART(port[4:]) if port.startswith('hid:') else UART(port)
    if not ser.sync(): sys.exit("MCU sync failed")
    if args.debug:
        src="keyboard" if args.keyboard else f"controller slot {pad.slot}"
        transport = "HID" if port.startswith('hid:') else "COM"
        print(f"Using {src} → {transport} {port} @ {BAUD_DEF} baud")

    neutral=Packet(0,8,0,0,0,0)
    was_focused=True
    try:
        while True:
            if not pad.ok():
                ser.write(neutral.pack())
                if args.debug: print("Pad lost – neutral")
                time.sleep(RETRY)
                pad=PadK(center) if args.keyboard else PadX(args.controller if args.controller is not None else 0)
                continue
            if not ((not args.window) or focus_ok(args.window)):
                if was_focused and args.debug: print("Window inactive – neutral")
                ser.write(neutral.pack()); was_focused=False; time.sleep(SEND); continue
            if not was_focused and args.debug: print("Window active – streaming")
            was_focused=True
            pkt,bits=build_packet(pad)
            ser.write(pkt.pack())
            if args.debug: print(f"buttons=0x{bits:04X} raw=0x{pad.raw():04X} pkt={pkt.pack().hex()}")
            time.sleep(SEND)
    except KeyboardInterrupt:
        pass
    finally:
        ser.close()
