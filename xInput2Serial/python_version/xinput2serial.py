import argparse
import os
import sys
import serial
import serial.tools.list_ports
import time
import ctypes

# Ensure pygame can run headless
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
if sys.platform == "win32":
    # Detect virtual controllers like Moonlight's "RAW INPUT" device
    os.environ.setdefault("SDL_JOYSTICK_RAWINPUT", "1")

try:
    import pygame
    import pygame.joystick
except ImportError:
    pygame = None

try:
    import win32gui
except ImportError:
    win32gui = None

class XInputJoystick:
    """Minimal XInput wrapper providing pygame-like API on Windows."""

    BUTTONS = [
        0x1000,  # A
        0x2000,  # B
        0x4000,  # X
        0x8000,  # Y
        0x0100,  # LB
        0x0200,  # RB
        0x0020,  # BACK
        0x0010,  # START
        0x0400,  # GUIDE
        0x0040,  # LTHUMB
        0x0080,  # RTHUMB
    ]

    def __init__(self, index: int = 0):
        self.index = index
        for dll in ("xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll"):
            try:
                self.xinput = ctypes.windll.LoadLibrary(dll)
                break
            except OSError:
                self.xinput = None
        if not getattr(self, "xinput", None):
            raise RuntimeError("XInput DLL not found")

        class GAMEPAD(ctypes.Structure):
            _fields_ = [
                ("wButtons", ctypes.c_ushort),
                ("bLeftTrigger", ctypes.c_ubyte),
                ("bRightTrigger", ctypes.c_ubyte),
                ("sThumbLX", ctypes.c_short),
                ("sThumbLY", ctypes.c_short),
                ("sThumbRX", ctypes.c_short),
                ("sThumbRY", ctypes.c_short),
            ]

        class STATE(ctypes.Structure):
            _fields_ = [
                ("dwPacketNumber", ctypes.c_uint),
                ("Gamepad", GAMEPAD),
            ]

        self._STATE = STATE
        self._state = STATE()

    def _poll(self) -> bool:
        res = self.xinput.XInputGetState(self.index, ctypes.byref(self._state))
        return res == 0

    def get_button(self, index: int) -> int:
        if not self._poll():
            return 0
        return 1 if (self._state.Gamepad.wButtons & self.BUTTONS[index]) else 0

    def get_axis(self, index: int) -> float:
        if not self._poll():
            return 0.0
        gp = self._state.Gamepad
        if index == 0:
            return gp.sThumbLX / 32767.0
        if index == 1:
            return -gp.sThumbLY / 32767.0
        if index == 2:
            return gp.bLeftTrigger / 255.0
        if index == 3:
            return gp.sThumbRX / 32767.0
        if index == 4:
            return -gp.sThumbRY / 32767.0
        if index == 5:
            return gp.bRightTrigger / 255.0
        return 0.0

    def get_numhats(self):
        return 1

    def get_hat(self, index: int):
        if not self._poll():
            return (0, 0)
        w = self._state.Gamepad.wButtons
        x = (1 if w & 0x0008 else 0) + (-1 if w & 0x0004 else 0)
        y = (1 if w & 0x0001 else 0) + (-1 if w & 0x0002 else 0)
        return (x, y)


COMMAND_SYNC_1 = 0x33
COMMAND_SYNC_2 = 0xCC
COMMAND_SYNC_START = 0xFF
RESP_SYNC_START = 0xFF
RESP_SYNC_1 = 0xCC
RESP_SYNC_OK = 0x33

DEFAULT_BAUDRATE = 1_000_000


def crc8_ccitt(data: bytes) -> int:
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 0x07) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc


class SerialAdapter:
    def __init__(self, port: str, baudrate: int = DEFAULT_BAUDRATE):
        self.serial = serial.Serial(port, baudrate=baudrate, timeout=0.05)

    def write(self, data: bytes):
        data += bytes([crc8_ccitt(data)])
        self.serial.write(data)

    def read(self, size: int = 1) -> bytes:
        return self.serial.read(size)

    def sync(self, debug: bool = False) -> bool:
        self.serial.write(bytes([COMMAND_SYNC_START]) * 9)
        start = time.time()
        stage = 0
        while time.time() - start < 1.0:
            if self.serial.in_waiting:
                data = self.serial.read(self.serial.in_waiting)
                if data and data[-1] == RESP_SYNC_START:
                    stage = 1
                    self.serial.write(bytes([COMMAND_SYNC_1]))
                    resp = self.serial.read(1)
                    if resp and resp[0] == RESP_SYNC_1:
                        stage = 2
                        self.serial.write(bytes([COMMAND_SYNC_2]))
                        resp = self.serial.read(1)
                        if resp and resp[0] == RESP_SYNC_OK:
                            return True
        if debug:
            print(f"Sync failed at stage {stage}")
        return False

    def close(self):
        self.serial.close()


class Packet:
    def __init__(self, buttons: int, dpad: int, lx: float, ly: float, rx: float, ry: float):
        self.buttons = buttons
        self.dpad = dpad
        self.lx = lx
        self.ly = ly
        self.rx = rx
        self.ry = ry

    def to_bytes(self) -> bytes:
        buf = bytearray(8)
        buf[0] = (self.buttons >> 8) & 0xFF
        buf[1] = self.buttons & 0xFF
        buf[2] = self.dpad & 0xFF
        buf[3] = int((self.lx + 1) / 2 * 255) & 0xFF
        buf[4] = int((self.ly + 1) / 2 * 255) & 0xFF
        buf[5] = int((self.rx + 1) / 2 * 255) & 0xFF
        buf[6] = int((self.ry + 1) / 2 * 255) & 0xFF
        buf[7] = 0
        # center deadzone
        if abs(buf[3] - 0x80) < 10:
            buf[3] = 0x80
        if abs(buf[4] - 0x80) < 10:
            buf[4] = 0x80
        if abs(buf[5] - 0x80) < 10:
            buf[5] = 0x80
        if abs(buf[6] - 0x80) < 10:
            buf[6] = 0x80
        return bytes(buf)

    def __repr__(self) -> str:
        return (
            f"Packet(buttons=0x{self.buttons:04X}, dpad=0x{self.dpad:02X}, "
            f"lx={self.lx:.2f}, ly={self.ly:.2f}, rx={self.rx:.2f}, ry={self.ry:.2f})"
        )


def parse_args():
    parser = argparse.ArgumentParser(description="xinput to serial")
    parser.add_argument('--port')
    parser.add_argument('--baudrate', type=int, default=DEFAULT_BAUDRATE)
    parser.add_argument('--controller', type=int)
    parser.add_argument('--window')
    parser.add_argument('--auto', action='store_true')
    parser.add_argument('--debug', action='store_true')
    return parser.parse_args()


def get_first_serial_port(debug: bool = False) -> str | None:
    ports = list(serial.tools.list_ports.comports())
    if debug:
        for p in ports:
            print(f"Found serial port: {p.device}")
    return ports[0].device if ports else None


def get_joystick(index: int | None = None, debug: bool = False):
    """Return a joystick object using XInput on Windows or pygame elsewhere."""
    if sys.platform == "win32":
        try:
            joy = XInputJoystick(index if index is not None else 0)
            if debug:
                print("Using XInput for controller", joy.index)
            return joy
        except Exception as exc:
            if debug:
                print("XInput unavailable:", exc)
    if pygame is None:
        raise RuntimeError('pygame is required')
    pygame.joystick.init()
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    count = pygame.joystick.get_count()
    if debug:
        print(f"Detected {count} joystick(s)")
        for i in range(count):
            j = pygame.joystick.Joystick(i)
            j.init()
            print(f"  {i}: {j.get_name()}")
            j.quit()
    if count == 0:
        return None
    idx = index if index is not None else 0
    joy = pygame.joystick.Joystick(idx)
    joy.init()
    return joy


def is_window_active(title: str) -> bool:
    """Return True if a window with the given title currently has focus."""
    if win32gui is None:
        return True
    hwnd = win32gui.GetForegroundWindow()
    active = win32gui.GetWindowText(hwnd)
    return title.lower() in active.lower()


# Button mapping constants
BTN_MAPPING = {
    0: 1 << 2,  # A -> B
    1: 1 << 0,  # B -> Y
    2: 1 << 3,  # X -> X
    3: 1 << 1,  # Y -> A
    4: 1 << 4,  # LB -> L
    5: 1 << 5,  # RB -> R
    6: 1 << 8,  # Back -> MINUS
    7: 1 << 9,  # Start -> PLUS
    8: 1 << 12, # Xbox -> HOME
    9: 1 << 10, # LStick
    10: 1 << 11, # RStick
}

DPAD_MAPPING = {
    (0, 1): 0x00,  # up
    (1, 1): 0x01,
    (1, 0): 0x02,
    (1, -1): 0x03,
    (0, -1): 0x04,
    (-1, -1): 0x05,
    (-1, 0): 0x06,
    (-1, 1): 0x07,
    (0, 0): 0x08,
}


def build_packet(joy) -> Packet:
    if pygame and hasattr(joy, 'get_id'):
        pygame.event.pump()
    buttons = 0
    for btn_idx, mask in BTN_MAPPING.items():
        if joy.get_button(btn_idx):
            buttons |= mask
    # triggers as ZL/ZR
    if joy.get_axis(2) > 0.5:
        buttons |= 1 << 6
    if joy.get_axis(5) > 0.5:
        buttons |= 1 << 7

    hatx, haty = (0, 0)
    if joy.get_numhats() > 0:
        hatx, haty = joy.get_hat(0)
    dpad = DPAD_MAPPING.get((hatx, haty), 0x08)
    lx = joy.get_axis(0)
    ly = joy.get_axis(1)
    rx = joy.get_axis(3)
    ry = joy.get_axis(4)
    return Packet(buttons, dpad, lx, ly, rx, ry)


def main():
    args = parse_args()

    if args.window and win32gui is None:
        print("Error: --window requires the pywin32 package (win32gui module)")
        return

    port = args.port or get_first_serial_port(args.debug)
    joy = get_joystick(args.controller, args.debug)

    if args.auto:
        if port is None:
            raise RuntimeError('No serial port found')
        if joy is None:
            raise RuntimeError('No controller found')
    else:
        if port is None or joy is None:
            print('No serial port or controller available')
            return

    if args.debug:
        print(f"Using serial port {port} at {args.baudrate} baud")
    adapter = SerialAdapter(port, args.baudrate)
    if args.debug:
        print("Waiting for device...")
    if not adapter.sync(args.debug):
        print('Failed to sync with device')
        adapter.close()
        return
    if args.debug:
        print("Device synchronized")

    try:
        prev_active = True
        neutral = Packet(0, 0x08, 0, 0, 0, 0)
        while True:
            active = not args.window or is_window_active(args.window)
            if not active:
                if prev_active:
                    adapter.write(neutral.to_bytes())
                    if args.debug:
                        print("Window inactive - TX:", neutral.to_bytes().hex())
                    prev_active = False
                time.sleep(0.1)
                continue

            prev_active = True
            packet = build_packet(joy)
            adapter.write(packet.to_bytes())
            if args.debug:
                print("TX:", packet.to_bytes().hex(), packet)
            time.sleep(0.01)
    except KeyboardInterrupt:
        pass
    finally:
        adapter.close()


if __name__ == '__main__':
    main()

