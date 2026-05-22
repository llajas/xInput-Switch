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

import argparse, ctypes, json, os, socket, sys, threading, time, warnings
from datetime import datetime
from pathlib import Path
import serial, serial.tools.list_ports

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
try:
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    warnings.filterwarnings("ignore", message="pkg_resources is deprecated as an API.*")
    import pygame
    import pygame._sdl2.controller as sdl_controller
except ImportError:
    pygame = None
    sdl_controller = None

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
    def __init__(self, port: str, baud: int):
        self.h = serial.Serial(port, baudrate=baud, timeout=0.05)
    def write(self, p: bytes):
        self.h.write(p + bytes([crc8(p)]))
    def read_until_quiet(self, quiet_seconds=0.05, max_seconds=1.0):
        data = bytearray()
        deadline = time.time() + max_seconds
        quiet_deadline = time.time() + quiet_seconds
        while time.time() < deadline:
            b = self.h.read(1)
            if b:
                data.extend(b)
                quiet_deadline = time.time() + quiet_seconds
            elif time.time() >= quiet_deadline:
                break
        return bytes(data)
    def read_expected(self, expected: int, log=None, label="response", timeout=1.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            b = self.h.read(1)
            if not b:
                continue
            if b[0] == expected:
                return True
            if log:
                log(f"MCU sync: ignoring byte 0x{b[0]:02X} while waiting for {label} 0x{expected:02X}.")
        if log:
            log(f"MCU sync: timed out waiting for {label} 0x{expected:02X}.")
        return False
    def sync(self, log=None) -> bool:
        self.h.reset_input_buffer()
        self.h.write(bytes([CMD_ST]) * 9)
        start_responses = self.read_until_quiet()
        if log:
            if start_responses:
                log(f"MCU sync: received start response bytes {start_responses.hex(' ')}.")
            else:
                log("MCU sync: received no start response bytes.")
        if RSP_ST not in start_responses:
            return False

        self.h.write(bytes([CMD1]))
        if not self.read_expected(RSP1, log, "command 1 response"):
            return False
        if log:
            log("MCU sync: received command 1 response.")

        self.h.write(bytes([CMD2]))
        if not self.read_expected(RSP_OK, log, "final OK"):
            return False
        return True
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
    def label(self): return f"XInput controller slot {self.slot}"
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

# SDL controller backend. SDL normalizes DS4, Xbox, and many other pads to a common gamepad layout.
SDL_BUTTONS = None
SDL_AXES = None

def init_sdl():
    global SDL_BUTTONS, SDL_AXES
    if pygame is None or sdl_controller is None:
        return False
    if not pygame.get_init():
        pygame.init()
    try:
        sdl_controller.init()
    except Exception:
        return False
    SDL_BUTTONS = [
        pygame.CONTROLLER_BUTTON_A,
        pygame.CONTROLLER_BUTTON_B,
        pygame.CONTROLLER_BUTTON_X,
        pygame.CONTROLLER_BUTTON_Y,
        pygame.CONTROLLER_BUTTON_LEFTSHOULDER,
        pygame.CONTROLLER_BUTTON_RIGHTSHOULDER,
        pygame.CONTROLLER_BUTTON_BACK,
        pygame.CONTROLLER_BUTTON_START,
        pygame.CONTROLLER_BUTTON_GUIDE,
        pygame.CONTROLLER_BUTTON_LEFTSTICK,
        pygame.CONTROLLER_BUTTON_RIGHTSTICK,
    ]
    SDL_AXES = [
        pygame.CONTROLLER_AXIS_LEFTX,
        pygame.CONTROLLER_AXIS_LEFTY,
        pygame.CONTROLLER_AXIS_TRIGGERLEFT,
        pygame.CONTROLLER_AXIS_RIGHTX,
        pygame.CONTROLLER_AXIS_RIGHTY,
        pygame.CONTROLLER_AXIS_TRIGGERRIGHT,
    ]
    return True

def norm_sdl_axis(value):
    if value < 0:
        return max(-1.0, value / 32768.0)
    return min(1.0, value / 32767.0)

def norm_sdl_trigger(value):
    # SDL controllers usually expose triggers as 0..32767, but some virtual devices use -32768..32767.
    if value < 0:
        return max(0.0, min(1.0, (value + 32768) / 65535.0))
    return max(0.0, min(1.0, value / 32767.0))

class PadSDL:
    def __init__(self, index: int):
        if not init_sdl():
            raise RuntimeError("pygame SDL controller backend is unavailable")
        if index < 0 or index >= sdl_controller.get_count():
            raise RuntimeError(f"SDL controller index {index} is out of range")
        if not sdl_controller.is_controller(index):
            raise RuntimeError(f"SDL device {index} is not recognized as a game controller")
        self.index = index
        self.ctrl = sdl_controller.Controller(index)
        self.ctrl.init()
        self.name = self.ctrl.name
    def label(self): return f"SDL controller {self.index}: {self.name}"
    def ok(self):
        if pygame:
            pygame.event.pump()
        return self.ctrl.attached()
    def btn(self,i):
        if pygame:
            pygame.event.pump()
        return bool(self.ctrl.get_button(SDL_BUTTONS[i]))
    def axis(self,i):
        if pygame:
            pygame.event.pump()
        value = self.ctrl.get_axis(SDL_AXES[i])
        if i in (2, 5):
            return norm_sdl_trigger(value)
        normalized = norm_sdl_axis(value)
        if i in (1, 4):
            return -normalized
        return normalized
    def hat(self):
        x = (1 if self.ctrl.get_button(pygame.CONTROLLER_BUTTON_DPAD_RIGHT) else 0) + (-1 if self.ctrl.get_button(pygame.CONTROLLER_BUTTON_DPAD_LEFT) else 0)
        y = (1 if self.ctrl.get_button(pygame.CONTROLLER_BUTTON_DPAD_UP) else 0) + (-1 if self.ctrl.get_button(pygame.CONTROLLER_BUTTON_DPAD_DOWN) else 0)
        return (x, y)
    def raw(self):
        bits = 0
        for i, button in enumerate(SDL_BUTTONS):
            if self.ctrl.get_button(button):
                bits |= 1 << i
        return bits

# Local socket backend for external input adapters such as Discord bots.
SOCKET_BUTTONS = {
    "b": 0,
    "a": 1,
    "y": 2,
    "x": 3,
    "l": 4,
    "r": 5,
    "minus": 6,
    "select": 6,
    "back": 6,
    "plus": 7,
    "start": 7,
    "lclick": 9,
    "ls": 9,
    "rclick": 10,
    "rs": 10,
}
SOCKET_EXTRA_BITS = {
    "home": 1 << 12,
    "capture": 1 << 13,
    "screenshot": 1 << 13,
}
SOCKET_TRIGGER_AXES = {
    "zl": 2,
    "lt": 2,
    "zr": 5,
    "rt": 5,
}
SOCKET_DPAD = {
    "up": (0, 1),
    "u": (0, 1),
    "down": (0, -1),
    "d": (0, -1),
    "right": (1, 0),
    "r": (1, 0),
    "left": (-1, 0),
    "l": (-1, 0),
    "up-right": (1, 1),
    "upright": (1, 1),
    "ur": (1, 1),
    "up-left": (-1, 1),
    "upleft": (-1, 1),
    "ul": (-1, 1),
    "down-right": (1, -1),
    "downright": (1, -1),
    "dr": (1, -1),
    "down-left": (-1, -1),
    "downleft": (-1, -1),
    "dl": (-1, -1),
}

class PadSocket:
    def __init__(self, host, port, log=None, status_file=None):
        self.host = host
        self.port = port
        self.log = log or (lambda _msg: None)
        self.status_file = Path(status_file) if status_file else None
        self.lock = threading.Lock()
        self.button_until = {}
        self.extra_until = {}
        self.axis_until = {}
        self.hat_until = 0.0
        self.hat_value = (0, 0)
        self.active_peers = 0
        self.total_connections = 0
        self.total_events = 0
        self.last_peer = ""
        self.last_event = ""
        self.last_event_at = ""
        self.running = True
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()
        self.log(f"Socket input listening on {host}:{port}.")
        self._write_status("listening")

    def label(self): return f"socket input {self.host}:{self.port}"
    def ok(self): return self.running
    def raw(self): return 0

    def btn(self, i):
        self._expire()
        return self.button_until.get(i, 0.0) > time.time()

    def extra_buttons(self):
        self._expire()
        now = time.time()
        bits = 0
        for bit, until in self.extra_until.items():
            if until > now:
                bits |= bit
        return bits

    def axis(self, i):
        self._expire()
        value, until = self.axis_until.get(i, (0.0, 0.0))
        return value if until > time.time() else 0.0

    def hat(self):
        self._expire()
        return self.hat_value if self.hat_until > time.time() else (0, 0)

    def _expire(self):
        now = time.time()
        with self.lock:
            self.button_until = {k: v for k, v in self.button_until.items() if v > now}
            self.extra_until = {k: v for k, v in self.extra_until.items() if v > now}
            self.axis_until = {k: v for k, v in self.axis_until.items() if v[1] > now}
            if self.hat_until <= now:
                self.hat_value = (0, 0)

    def _write_status(self, state=None):
        if not self.status_file:
            return
        with self.lock:
            data = {
                "state": state or ("listening" if self.running else "stopped"),
                "host": self.host,
                "port": self.port,
                "activePeers": self.active_peers,
                "totalConnections": self.total_connections,
                "totalEvents": self.total_events,
                "lastPeer": self.last_peer,
                "lastEvent": self.last_event,
                "lastEventAt": self.last_event_at,
                "updatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
            }
        try:
            self.status_file.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.status_file.with_name(f"{self.status_file.name}.{os.getpid()}.tmp")
            tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            tmp.replace(self.status_file)
        except OSError as exc:
            self.log(f"Socket status write failed: {exc}")

    def _serve(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
                server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server.bind((self.host, self.port))
                server.listen()
                self._write_status("listening")
                while self.running:
                    conn, addr = server.accept()
                    with self.lock:
                        self.active_peers += 1
                        self.total_connections += 1
                        self.last_peer = f"{addr[0]}:{addr[1]}"
                    self.log(f"Socket peer connected: {addr[0]}:{addr[1]}.")
                    self._write_status("connected")
                    threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True).start()
        except OSError as exc:
            self.running = False
            self.log(f"Socket input stopped: {exc}")
            self._write_status("stopped")

    def _handle_client(self, conn, addr):
        try:
            with conn:
                buf = b""
                while True:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        self._handle_line(line.decode("utf-8", errors="replace").strip(), addr)
        finally:
            with self.lock:
                self.active_peers = max(0, self.active_peers - 1)
            self.log(f"Socket peer disconnected: {addr[0]}:{addr[1]}.")
            self._write_status("listening")

    def _handle_line(self, line, addr):
        if not line:
            return
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            event = {"command": line}
        with self.lock:
            self.total_events += 1
            self.last_peer = f"{addr[0]}:{addr[1]}"
            self.last_event = str(event.get("command") or event.get("button") or event.get("dpad") or event.get("buttons") or event.get("commands") or "input")
            self.last_event_at = datetime.now().astimezone().isoformat(timespec="seconds")
        self.apply_event(event)
        self._write_status("connected")

    def apply_event(self, event):
        duration = max(0.01, min(float(event.get("duration", 0.2)), 5.0))
        until = time.time() + duration

        commands = []
        for key in ("command", "button", "dpad"):
            value = event.get(key)
            if value:
                commands.append(str(value))
        for key in ("buttons", "commands"):
            values = event.get(key) or []
            if isinstance(values, str):
                values = [values]
            commands.extend(str(v) for v in values)

        with self.lock:
            for command in commands:
                self._apply_command(command, until)

            left = event.get("left")
            right = event.get("right")
            if event.get("stick") and ("x" in event or "y" in event):
                stick = str(event.get("stick")).lower()
                target = {"x": event.get("x", 0), "y": event.get("y", 0)}
                if stick in ("left", "l"):
                    left = target
                elif stick in ("right", "r"):
                    right = target
            if isinstance(left, dict):
                self.axis_until[0] = (self._clamp_axis(left.get("x", 0)), until)
                self.axis_until[1] = (self._clamp_axis(left.get("y", 0)), until)
            if isinstance(right, dict):
                self.axis_until[3] = (self._clamp_axis(right.get("x", 0)), until)
                self.axis_until[4] = (self._clamp_axis(right.get("y", 0)), until)

    def _apply_command(self, command, until):
        name = command.strip().lower().replace(" ", "-")
        if name in SOCKET_DPAD:
            self.hat_value = SOCKET_DPAD[name]
            self.hat_until = until
        elif name in SOCKET_BUTTONS:
            self.button_until[SOCKET_BUTTONS[name]] = until
        elif name in SOCKET_EXTRA_BITS:
            self.extra_until[SOCKET_EXTRA_BITS[name]] = until
        elif name in SOCKET_TRIGGER_AXES:
            self.axis_until[SOCKET_TRIGGER_AXES[name]] = (1.0, until)

    def _clamp_axis(self, value):
        try:
            return max(-1.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.0

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
    def label(self): return "keyboard/mouse"
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
SWITCH_HOME = 1 << 12

def exit_chord_pressed(p):
    if not isinstance(p, (PadX, PadSDL)):
        return False
    return (
        p.btn(4) and
        p.btn(5) and
        p.btn(6) and
        p.axis(2) > 0.5 and
        p.axis(5) > 0.5
    )

def write_exit_signal(path, log):
    if not path:
        return
    signal_path = Path(path)
    try:
        signal_path.parent.mkdir(parents=True, exist_ok=True)
        signal_path.write_text(f"{datetime.now().astimezone().isoformat(timespec='seconds')}\n", encoding="utf-8")
        log(f"Session exit signal written to {signal_path}.")
    except OSError as exc:
        log(f"Unable to write session exit signal to {signal_path}: {exc}")

def build_packet(p):
    b=0
    for i,m in BTN_MAP.items():
        if p.btn(i): b|=m
    if isinstance(p,PadK):
        if keyboard and keyboard.is_pressed('h'): b|=1<<12
        if keyboard and keyboard.is_pressed('c'): b|=1<<13
    if hasattr(p, "extra_buttons"):
        b |= p.extra_buttons()
    if isinstance(p,(PadX,PadSDL)) and ((p.btn(6) and p.btn(7)) or p.btn(8)): b|=1<<12
    if isinstance(p,(PadX,PadSDL)):
        if p.axis(2)>0.5: b|=1<<6
        if p.axis(5)>0.5: b|=1<<7
    elif isinstance(p,PadK):
        if keyboard and keyboard.is_pressed('shift'): b|=1<<6
        if keyboard and keyboard.is_pressed('ctrl'):  b|=1<<7
    hx,hy=p.hat()
    return Packet(b,HAT_MAP[(hx,hy)],p.axis(0),p.axis(1),p.axis(3),p.axis(4)), b

def describe_ports():
    return [
        f"{p.device} | {p.description} | {p.hwid}"
        for p in serial.tools.list_ports.comports()
    ]

list_ports=lambda:[p.device for p in serial.tools.list_ports.comports()]
def foreground_title():
    if win32gui is None:
        return ""
    return win32gui.GetWindowText(win32gui.GetForegroundWindow())

def focus_ok(title:str):
    if win32gui is None: return True
    return title.lower() in foreground_title().lower()

def make_logger(path):
    if not path:
        return lambda _msg: None
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    def _log(msg):
        line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
        print(line, flush=True)
        try:
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError as exc:
            print(f"[logger] unable to write to {log_path}: {exc}", flush=True)
    return _log

def detect_controller_slot(log):
    if _x is None:
        log("No XInput DLL could be loaded.")
        return None
    for slot in range(4):
        pad = PadX(slot)
        if pad.ok():
            log(f"Detected XInput controller in slot {slot}.")
            return slot
        log(f"No XInput controller in slot {slot}.")
    return None

def describe_sdl_controllers(log):
    if not init_sdl():
        log("pygame SDL controller backend is unavailable.")
        return
    count = sdl_controller.get_count()
    log(f"SDL controller devices: {count}")
    if count == 0:
        return
    for index in range(count):
        is_controller = sdl_controller.is_controller(index)
        try:
            name = sdl_controller.name_forindex(index)
        except Exception as exc:
            name = f"<name unavailable: {exc}>"
        log(f"  SDL {index}: controller={is_controller} name={name}")

def detect_sdl_controller_index(log):
    if not init_sdl():
        log("pygame SDL controller backend is unavailable.")
        return None
    for index in range(sdl_controller.get_count()):
        if sdl_controller.is_controller(index):
            try:
                pad = PadSDL(index)
                if pad.ok():
                    log(f"Detected SDL controller {index}: {pad.name}.")
                    return index
            except Exception as exc:
                log(f"SDL controller {index} could not be opened: {exc}")
        else:
            log(f"SDL device {index} is not recognized as a game controller.")
    return None

def create_controller(args, log):
    backend = args.backend
    selected = args.controller

    if backend == "socket":
        return PadSocket(args.socket_host, args.socket_port, log, args.socket_status_file)

    if backend in ("xinput", "auto"):
        controller_slot = selected
        if controller_slot is None and args.auto:
            controller_slot = detect_controller_slot(log)
        if controller_slot is not None:
            pad = PadX(controller_slot)
            if pad.ok():
                if args.startup_debug:
                    log(f"Using XInput controller slot {pad.slot}.")
                return pad
            if backend == "xinput":
                log("Selected XInput controller is not connected.")

    if backend in ("pygame", "auto"):
        controller_index = selected
        if controller_index is None and args.auto:
            controller_index = detect_sdl_controller_index(log)
        if controller_index is not None:
            try:
                pad = PadSDL(controller_index)
                if pad.ok():
                    if args.startup_debug:
                        log(f"Using SDL controller {pad.index}: {pad.name}.")
                    return pad
            except Exception as exc:
                log(f"Selected SDL controller could not be opened: {exc}")

    return None

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--keyboard",action="store_true")
    ap.add_argument("--port")
    ap.add_argument("--baud",type=int,default=BAUD_DEF)
    ap.add_argument("--controller",type=int)
    ap.add_argument("--backend",choices=("auto","xinput","pygame","socket"),default="xinput")
    ap.add_argument("--socket-host",default="127.0.0.1")
    ap.add_argument("--socket-port",type=int,default=8765)
    ap.add_argument("--socket-status-file")
    ap.add_argument("--window")
    ap.add_argument("--auto",action="store_true")
    ap.add_argument("--debug",action="store_true")
    ap.add_argument("--log-file")
    ap.add_argument("--startup-debug",action="store_true")
    ap.add_argument("--diagnose",action="store_true",help="Print COM and XInput detection details, then exit.")
    ap.add_argument("--sync-attempts",type=int,default=3)
    ap.add_argument("--inactive-action",choices=("neutral","home","none"),default="neutral")
    ap.add_argument("--disconnect-action",choices=("neutral","home","none"),default="neutral")
    ap.add_argument("--home-duration",type=float,default=0.25)
    ap.add_argument("--home-cooldown",type=float,default=5.0)
    ap.add_argument("--exit-chord-signal-file")
    args=ap.parse_args()
    log = make_logger(args.log_file)

    if args.startup_debug or args.diagnose:
        log("xinput2serial starting.")
        log("Serial ports:")
        port_infos = describe_ports()
        for port_info in port_infos:
            log(f"  {port_info}")
        if not port_infos:
            log("  none")

    if args.diagnose:
        detect_controller_slot(log)
        describe_sdl_controllers(log)
        log("Diagnostics complete.")
        sys.exit(0)

    center=None
    if args.keyboard and args.window and win32gui:
        hwnd=win32gui.FindWindow(None,args.window)
        if hwnd:
            l,t,r,b=win32gui.GetWindowRect(hwnd)
            cx,cy=(l+r)//2,(t+b)//2
            center=(cx,cy)
            if args.startup_debug:
                log(f"Keyboard/mouse center set to {center}.")
        elif args.startup_debug:
            log(f"Window not found for keyboard/mouse centering: {args.window}")

    port=args.port
    if not port and not args.auto:
        ports=list_ports(); port=ports[0] if ports else None
    if not port and args.auto:
        ports=list_ports(); port=ports[0] if ports else None
    if not port:
        log("No serial port selected.")
        sys.exit("No serial port selected")
    if args.startup_debug:
        log(f"Using serial port {port} at {args.baud} baud.")

    if args.keyboard:
        pad=PadK(center)
    else:
        pad=create_controller(args, log)
        if pad is None:
            log(f"No controller selected or detected for backend '{args.backend}'.")
            sys.exit("Controller not connected")
    if not pad.ok():
        log("Controller not connected.")
        sys.exit("Controller not connected")

    try:
        ser=UART(port,args.baud)
    except Exception as exc:
        log(f"Serial open failed on {port}: {exc}")
        raise
    synced = False
    for attempt in range(1, args.sync_attempts + 1):
        if args.startup_debug:
            log(f"Attempting MCU sync ({attempt}/{args.sync_attempts}).")
        if ser.sync(log if args.startup_debug else None):
            synced = True
            break
        time.sleep(0.25)
    if not synced:
        log("MCU sync failed.")
        sys.exit("MCU sync failed")
    if args.startup_debug:
        log("MCU sync succeeded.")
    if args.debug:
        src=pad.label() if hasattr(pad, "label") else "controller"
        print(f"Using {src} -> COM {port} @ {args.baud} baud")

    neutral=Packet(0,8,0,0,0,0)
    home=Packet(SWITCH_HOME,8,0,0,0,0)
    was_focused=True
    last_focus_state=None
    inactive_home_until=0.0
    last_disconnect_home=0.0
    disconnect_home_until=0.0
    try:
        while True:
            now=time.time()
            if not pad.ok():
                if args.disconnect_action == "home" and now - last_disconnect_home >= args.home_cooldown:
                    last_disconnect_home = now
                    disconnect_home_until = now + args.home_duration
                    if args.debug: print("Pad lost - HOME")
                if now < disconnect_home_until:
                    ser.write(home.pack())
                elif args.disconnect_action != "none":
                    ser.write(neutral.pack())
                    if args.debug: print("Pad lost - neutral")
                time.sleep(RETRY)
                pad=PadK(center) if args.keyboard else create_controller(args, log)
                if pad is None:
                    time.sleep(RETRY)
                    continue
                continue

            focused=(not args.window) or focus_ok(args.window)
            if last_focus_state is None or focused != last_focus_state:
                last_focus_state=focused
                if args.startup_debug:
                    state="active" if focused else "inactive"
                    log(f"Window focus is {state}. Foreground='{foreground_title()}'")

            if not focused:
                if was_focused and args.inactive_action == "home":
                    inactive_home_until = now + args.home_duration
                    if args.debug: print("Window inactive - HOME")
                elif was_focused and args.debug:
                    print("Window inactive - neutral")

                if now < inactive_home_until:
                    ser.write(home.pack())
                elif args.inactive_action != "none":
                    ser.write(neutral.pack())
                was_focused=False
                time.sleep(SEND)
                continue
            if not was_focused and args.debug: print("Window active - streaming")
            was_focused=True
            if args.exit_chord_signal_file and exit_chord_pressed(pad):
                log("Exit chord detected; sending HOME pulse and ending session.")
                end = time.time() + args.home_duration
                while time.time() < end:
                    ser.write(home.pack())
                    time.sleep(SEND)
                ser.write(neutral.pack())
                write_exit_signal(args.exit_chord_signal_file, log)
                break
            pkt,bits=build_packet(pad)
            ser.write(pkt.pack())
            if args.debug: print(f"buttons=0x{bits:04X} raw=0x{pad.raw():04X} pkt={pkt.pack().hex()}")
            time.sleep(SEND)
    except KeyboardInterrupt:
        pass
    finally:
        ser.close()
