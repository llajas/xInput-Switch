#!/usr/bin/env python3
"""
Single entrypoint for Playnite.

Starts OBS if needed, opens the OBS projector, runs xinput2serial, watches the
projector window, then cleans up the bridge process and any OBS instance it
started.
"""

from __future__ import annotations

import argparse
import asyncio
import ctypes
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
import subprocess
import sys
import time

try:
    import simpleobsws
except ImportError:
    simpleobsws = None


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OBS_DIR = Path(r"C:\Program Files\obs-studio\bin\64bit")
DEFAULT_XINPUT = ROOT / "xInput2Serial" / "xinput2serial.py"
DEFAULT_LOG = Path(__file__).with_suffix(".log")
DEFAULT_PROJECTOR_TITLE = "Windowed Projector (Source) - Scene"
DEFAULT_SOURCE_NAME = "Scene"
DEFAULT_GEOMETRY = (
    "AdnQywADAAAAAAAIAAAAAAAAB3cAAAQvAAAACAAAAB8AAAeHAAAEQwAAAAAABAAAB4"
    "AAAAAAAAAAAAAAB38AAAQ3"
)

CREATE_NO_WINDOW = 0x08000000
WM_CLOSE = 0x0010

user32 = ctypes.windll.user32


def log(message: str, log_file: Path) -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}"
    try:
        print(line, flush=True)
    except OSError:
        pass
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def process_running(image_name: str) -> bool:
    result = subprocess.run(
        ["tasklist", "/NH", "/FI", f"IMAGENAME eq {image_name}"],
        capture_output=True,
        text=True,
        creationflags=CREATE_NO_WINDOW,
        check=False,
    )
    return image_name.lower() in result.stdout.lower()


def window_exists(title_part: str) -> bool:
    found = False
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
            found = True
            return False
        return True

    user32.EnumWindows(enum_proc, 0)
    return found


def close_windows_for_pid(pid: int) -> None:
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def enum_proc(hwnd, _lparam):
        window_pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
        if window_pid.value == pid:
            user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        return True

    user32.EnumWindows(enum_proc, 0)


async def open_projector(source_name: str, geometry: str, log_file: Path, timeout: int) -> None:
    if simpleobsws is None:
        raise RuntimeError("simpleobsws is not installed. Install it with: py -m pip install simpleobsws")

    params = simpleobsws.IdentificationParameters(ignoreNonFatalRequestChecks=False)
    client = simpleobsws.WebSocketClient(
        url="ws://127.0.0.1:4455",
        identification_parameters=params,
    )

    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            await client.connect()
            await client.wait_until_identified()
            break
        except Exception as exc:
            last_error = exc
            await asyncio.sleep(1)
    else:
        raise RuntimeError(f"OBS WebSocket did not become ready: {last_error}")

    data = {
        "sourceName": source_name,
        "projector": "windowed",
        "projectorGeometry": geometry,
    }
    result = await client.call(simpleobsws.Request("OpenSourceProjector", data))
    log(f"OpenSourceProjector result: {result}", log_file)
    await client.disconnect()


def start_obs(obs_dir: Path, log_file: Path) -> tuple[subprocess.Popen | None, bool]:
    if process_running("obs64.exe"):
        log("OBS is already running; leaving it open during cleanup.", log_file)
        return None, False

    obs_exe = obs_dir / "obs64.exe"
    if not obs_exe.exists():
        raise FileNotFoundError(f"OBS executable not found: {obs_exe}")

    log("Starting OBS.", log_file)
    proc = subprocess.Popen(
        [str(obs_exe), "--disable-shutdown-check"],
        cwd=str(obs_dir),
        creationflags=CREATE_NO_WINDOW,
    )
    return proc, True


def stop_process(proc: subprocess.Popen | None, name: str, log_file: Path) -> None:
    if proc is None or proc.poll() is not None:
        return

    log(f"Stopping {name}.", log_file)
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        log(f"Force-stopping {name}.", log_file)
        proc.kill()


def stop_obs(obs_proc: subprocess.Popen | None, log_file: Path) -> None:
    if obs_proc is None or obs_proc.poll() is not None:
        return

    log("Closing OBS.", log_file)
    close_windows_for_pid(obs_proc.pid)
    try:
        obs_proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        log("OBS did not close in time; terminating it.", log_file)
        obs_proc.terminate()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch Switch projector and xinput bridge.")
    parser.add_argument("--obs-dir", type=Path, default=DEFAULT_OBS_DIR)
    parser.add_argument("--xinput-script", type=Path, default=DEFAULT_XINPUT)
    parser.add_argument("--projector-title", default=DEFAULT_PROJECTOR_TITLE)
    parser.add_argument("--source-name", default=DEFAULT_SOURCE_NAME)
    parser.add_argument("--projector-geometry", default=DEFAULT_GEOMETRY)
    parser.add_argument("--log-file", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--startup-timeout", type=int, default=30)
    parser.add_argument("--keyboard", action="store_true", help="Use keyboard/mouse mode in xinput2serial.")
    parser.add_argument("--debug", action="store_true", help="Enable xinput2serial debug logging.")
    parser.add_argument("--port", help="Serial port to pass to xinput2serial, for example COM3.")
    parser.add_argument("--controller", type=int, help="XInput controller slot to pass to xinput2serial.")
    parser.add_argument(
        "--close-existing-obs",
        action="store_true",
        help="Close OBS on exit even if it was already running before this launcher started.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.log_file.parent.mkdir(parents=True, exist_ok=True)

    obs_proc = None
    started_obs = False
    xinput_proc = None

    try:
        obs_proc, started_obs = start_obs(args.obs_dir, args.log_file)
        asyncio.run(
            open_projector(
                args.source_name,
                args.projector_geometry,
                args.log_file,
                args.startup_timeout,
            )
        )

        xinput_cmd = [
            sys.executable,
            str(args.xinput_script),
            "--auto",
            "--window",
            args.projector_title,
        ]
        if args.keyboard:
            xinput_cmd.append("--keyboard")
        if args.debug:
            xinput_cmd.append("--debug")
        if args.port:
            xinput_cmd.extend(["--port", args.port])
        if args.controller is not None:
            xinput_cmd.extend(["--controller", str(args.controller)])

        log("Starting xinput2serial.", args.log_file)
        xinput_proc = subprocess.Popen(xinput_cmd, creationflags=CREATE_NO_WINDOW)

        deadline = time.monotonic() + args.startup_timeout
        while time.monotonic() < deadline:
            if window_exists(args.projector_title):
                break
            if xinput_proc.poll() is not None:
                raise RuntimeError(f"xinput2serial exited early with code {xinput_proc.returncode}")
            time.sleep(1)
        else:
            raise RuntimeError(f"Projector window never appeared: {args.projector_title}")

        log("Projector detected; monitoring until it closes.", args.log_file)
        while window_exists(args.projector_title):
            if xinput_proc.poll() is not None:
                raise RuntimeError(f"xinput2serial exited with code {xinput_proc.returncode}")
            time.sleep(1)

        log("Projector closed.", args.log_file)
        return 0
    except Exception as exc:
        log(f"ERROR: {exc}", args.log_file)
        return 1
    finally:
        stop_process(xinput_proc, "xinput2serial", args.log_file)
        if started_obs or args.close_existing_obs:
            stop_obs(obs_proc, args.log_file)
        log("Launcher finished.", args.log_file)


if __name__ == "__main__":
    raise SystemExit(main())
