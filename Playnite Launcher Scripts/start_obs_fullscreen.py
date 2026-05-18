import asyncio
import ctypes
import simpleobsws
import time
import sys
from ctypes import wintypes

# Define OBS WebSocket parameters
parameters = simpleobsws.IdentificationParameters(ignoreNonFatalRequestChecks=False)
ws = simpleobsws.WebSocketClient(url='ws://127.0.0.1:4455', identification_parameters=parameters)

user32 = ctypes.windll.user32
SW_SHOW = 5

def find_window_by_title(title_part):
    found = None
    needle = title_part.lower()

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def enum_proc(hwnd, _lparam):
        nonlocal found
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        if needle in buffer.value.lower():
            found = hwnd
            return False
        return True

    user32.EnumWindows(enum_proc, 0)
    return found

def focus_projector(timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        hwnd = find_window_by_title("Projector")
        if hwnd:
            user32.ShowWindow(hwnd, SW_SHOW)
            user32.SetForegroundWindow(hwnd)
            return True
        time.sleep(0.25)
    return False

async def open_projector():
    await ws.connect()
    await ws.wait_until_identified()

    # Open projector on specific source and geometry
    data = {
        'sourceName': 'Scene',       # OBS scene source name
        'projector': 'windowed',      # 'windowed' for projector, not fullscreen plugin
        'projectorGeometry': 'AdnQywADAAAAAAAIAAAAAAAAB3cAAAQvAAAACAAAAB8AAAeHAAAEQwAAAAAABAAAB4AAAAAAAAAAAAAAB38AAAQ3'
    }
    # Use the correct request for pop-up window projector
    request = simpleobsws.Request('OpenSourceProjector', data)
    result = await ws.call(request)
    print(f"OpenSourceProjector result: {result}")
    await ws.disconnect()

if __name__ == '__main__':
    time.sleep(2)
    try:
        asyncio.run(open_projector())
        if not focus_projector():
            print("Projector window was not found for focusing.")
    except Exception as e:
        print(f"OBS WS error: {e}")
        sys.exit(1)
    sys.exit(0)
