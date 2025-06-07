import argparse
import os
import sys
import serial
import serial.tools.list_ports
import time
import struct

if sys.platform == "win32":
    # Ensure SDL uses the raw input driver to detect virtual controllers like
    # Moonlight's "RAW INPUT" device.
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
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

    def sync(self) -> bool:
        self.serial.write(bytes([COMMAND_SYNC_START]) * 9)
        start = time.time()
        while time.time() - start < 1.0:
            if self.serial.in_waiting:
                data = self.serial.read(self.serial.in_waiting)
                if data and data[-1] == RESP_SYNC_START:
                    self.serial.write(bytes([COMMAND_SYNC_1]))
                    resp = self.serial.read(1)
                    if resp and resp[0] == RESP_SYNC_1:
                        self.serial.write(bytes([COMMAND_SYNC_2]))
                        resp = self.serial.read(1)
                        if resp and resp[0] == RESP_SYNC_OK:
                            return True
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


def parse_args():
    parser = argparse.ArgumentParser(description="xinput to serial")
    parser.add_argument('--port')
    parser.add_argument('--baudrate', type=int, default=DEFAULT_BAUDRATE)
    parser.add_argument('--controller', type=int)
    parser.add_argument('--window')
    parser.add_argument('--auto', action='store_true')
    return parser.parse_args()


def get_first_serial_port() -> str | None:
    ports = list(serial.tools.list_ports.comports())
    return ports[0].device if ports else None


def get_joystick(index: int | None = None):
    if pygame is None:
        raise RuntimeError('pygame is required')
    pygame.joystick.init()
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    if pygame.joystick.get_count() == 0:
        return None
    idx = index if index is not None else 0
    joy = pygame.joystick.Joystick(idx)
    joy.init()
    return joy


def is_window_active(title: str) -> bool:
    if win32gui is None:
        return True
    hwnd = win32gui.GetForegroundWindow()
    return win32gui.GetWindowText(hwnd) == title


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

    port = args.port or get_first_serial_port()
    joy = get_joystick(args.controller)

    if args.auto:
        if port is None:
            raise RuntimeError('No serial port found')
        if joy is None:
            raise RuntimeError('No controller found')
    else:
        if port is None or joy is None:
            print('No serial port or controller available')
            return

    adapter = SerialAdapter(port, args.baudrate)
    if not adapter.sync():
        print('Failed to sync with device')
        adapter.close()
        return

    try:
        while True:
            if args.window and not is_window_active(args.window):
                time.sleep(0.1)
                continue
            packet = build_packet(joy)
            adapter.write(packet.to_bytes())
            time.sleep(0.01)
    except KeyboardInterrupt:
        pass
    finally:
        adapter.close()


if __name__ == '__main__':
    main()

