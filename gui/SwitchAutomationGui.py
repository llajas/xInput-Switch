#!/usr/bin/env python3
import json
import os
import queue
import socket
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "switch_automation.settings.json"
BRIDGE_SCRIPT = ROOT / "xInput2Serial" / "xinput2serial.py"
PLAYNITE_LOG_DIR = ROOT / "Playnite Launcher Scripts"
DISCORD_BOT_SCRIPT = ROOT / "discord_input" / "discord_input_bot.py"
DISCORD_ENV_PATH = ROOT / "discord_input" / ".env"
DEFAULT_SOCKET_STATUS_FILE = PLAYNITE_LOG_DIR / "xinput2serial-socket-status.json"
DEFAULT_SESSION_EXIT_SIGNAL_FILE = PLAYNITE_LOG_DIR / "switch-session-exit.signal"

DEFAULT_SETTINGS = {
    "pythonExe": r"C:\Python312\python.exe",
    "obsDir": r"C:\Program Files\obs-studio\bin\64bit",
    "obsExe": r"C:\Program Files\obs-studio\bin\64bit\obs64.exe",
    "projectorTitle": "Projector",
    "playniteMode": "controller",
    "mode": "controller",
    "controllerBackend": "auto",
    "serialPort": "COM3",
    "controllerSlot": 0,
    "bindToProjectorFocus": True,
    "inactiveAction": "home",
    "disconnectAction": "home",
    "homeDuration": 0.25,
    "homeCooldown": 5.0,
    "debugBridge": False,
    "socketHost": "127.0.0.1",
    "socketPort": 8765,
    "socketStatusFile": str(DEFAULT_SOCKET_STATUS_FILE),
    "sessionExitSignalFile": str(DEFAULT_SESSION_EXIT_SIGNAL_FILE),
}


def load_settings():
    settings = dict(DEFAULT_SETTINGS)
    if CONFIG_PATH.exists():
        try:
            with CONFIG_PATH.open("r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                settings.update(loaded)
        except (OSError, json.JSONDecodeError) as exc:
            messagebox.showwarning("Settings", f"Unable to read settings:\n{exc}")
    return settings


def save_settings(settings):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8") as handle:
        json.dump(settings, handle, indent=2)
        handle.write("\n")


def list_serial_ports():
    try:
        import serial.tools.list_ports

        ports = [port.device for port in serial.tools.list_ports.comports()]
        return ports or ["COM3"]
    except ImportError:
        return ["COM3"]


def list_bind_addresses():
    choices = [
        ("Loopback only - 127.0.0.1", "127.0.0.1"),
        ("All IPv4 interfaces - 0.0.0.0", "0.0.0.0"),
    ]
    seen = {"127.0.0.1", "0.0.0.0"}

    try:
        command = [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-Command",
            (
                "Get-NetIPAddress -AddressFamily IPv4 | "
                "Where-Object { $_.IPAddress -notlike '169.254.*' -and $_.IPAddress -ne '127.0.0.1' } | "
                "Select-Object InterfaceAlias,IPAddress | ConvertTo-Json -Compress"
            ),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            if isinstance(data, dict):
                data = [data]
            for item in data:
                ip = str(item.get("IPAddress", "")).strip()
                alias = str(item.get("InterfaceAlias", "Adapter")).strip()
                if ip and ip not in seen:
                    choices.append((f"{alias} - {ip}", ip))
                    seen.add(ip)
    except Exception:
        pass

    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("169.254.") and ip not in seen:
                choices.append((f"Detected - {ip}", ip))
                seen.add(ip)
    except OSError:
        pass

    return choices


def update_env_file(path, updates):
    lines = []
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
    found = set()
    for index, line in enumerate(lines):
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if key in updates:
            lines[index] = f"{key}={updates[key]}"
            found.add(key)
    for key, value in updates.items():
        if key not in found:
            lines.append(f"{key}={value}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class SwitchAutomationGui(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Switch Automation")
        self.geometry("940x690")
        self.minsize(860, 620)
        self.bridge_process = None
        self.discord_process = None
        self.output_queue = queue.Queue()
        self.vars = {}
        self.bind_address_choices = []

        self._configure_style()
        self._build()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.reload_settings()
        self.after(100, self._drain_output)
        self.after(500, self._poll_socket_status)

    def _configure_style(self):
        self.style = ttk.Style(self)
        if "vista" in self.style.theme_names():
            self.style.theme_use("vista")
        self.style.configure("TFrame", padding=0)
        self.style.configure("Panel.TLabelframe", padding=12)
        self.style.configure("Mode.TRadiobutton", padding=(0, 4))

    def _build(self):
        root = ttk.Frame(self, padding=16)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=0)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(1, weight=1)

        header = ttk.Frame(root)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Switch Automation", font=("Segoe UI", 17, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Button(header, text="Save", command=self.save_current).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(header, text="Reload", command=self.reload_settings).grid(row=0, column=2, padx=(8, 0))

        mode_box = ttk.LabelFrame(root, text="Mode", style="Panel.TLabelframe")
        mode_box.grid(row=1, column=0, sticky="nsw", padx=(0, 12))
        self.vars["mode"] = tk.StringVar()
        modes = [
            ("Controller", "controller"),
            ("Discord / Socket", "socket"),
            ("Keyboard / Mouse", "keyboard"),
        ]
        for row, (label, value) in enumerate(modes):
            ttk.Radiobutton(
                mode_box,
                text=label,
                value=value,
                variable=self.vars["mode"],
                style="Mode.TRadiobutton",
                command=self._sync_mode_state,
            ).grid(row=row, column=0, sticky="w")

        main = ttk.Notebook(root)
        main.grid(row=1, column=1, sticky="nsew")

        settings_tab = ttk.Frame(main, padding=14)
        settings_tab.columnconfigure(1, weight=1)
        main.add(settings_tab, text="Settings")
        self._build_settings_tab(settings_tab)

        tools_tab = ttk.Frame(main, padding=14)
        tools_tab.rowconfigure(1, weight=1)
        tools_tab.columnconfigure(0, weight=1)
        main.add(tools_tab, text="Diagnostics")
        self._build_tools_tab(tools_tab)

        discord_tab = ttk.Frame(main, padding=14)
        discord_tab.columnconfigure(1, weight=1)
        discord_tab.rowconfigure(4, weight=1)
        main.add(discord_tab, text="Discord / Socket")
        self._build_discord_tab(discord_tab)

    def _build_settings_tab(self, parent):
        self.vars["pythonExe"] = tk.StringVar()
        self.vars["obsDir"] = tk.StringVar()
        self.vars["obsExe"] = tk.StringVar()
        self.vars["projectorTitle"] = tk.StringVar()
        self.vars["controllerBackend"] = tk.StringVar()
        self.vars["serialPort"] = tk.StringVar()
        self.vars["controllerSlot"] = tk.StringVar()
        self.vars["bindToProjectorFocus"] = tk.BooleanVar()
        self.vars["inactiveAction"] = tk.StringVar()
        self.vars["disconnectAction"] = tk.StringVar()
        self.vars["homeDuration"] = tk.StringVar()
        self.vars["homeCooldown"] = tk.StringVar()
        self.vars["debugBridge"] = tk.BooleanVar()
        self.vars["socketHost"] = tk.StringVar()
        self.vars["socketPort"] = tk.StringVar()
        self.vars["socketStatusFile"] = tk.StringVar()
        self.vars["sessionExitSignalFile"] = tk.StringVar()

        self._row(parent, 0, "Python", self._entry_with_browse(parent, "pythonExe", "Select Python executable"))
        self._row(parent, 1, "OBS Folder", self._folder_with_browse(parent, "obsDir"))
        self._row(parent, 2, "OBS Executable", self._entry_with_browse(parent, "obsExe", "Select OBS executable"))
        self._row(parent, 3, "Projector Title", ttk.Entry(parent, textvariable=self.vars["projectorTitle"]))

        self.controller_backend_combo = ttk.Combobox(
            parent,
            textvariable=self.vars["controllerBackend"],
            values=("auto", "xinput", "pygame"),
            state="readonly",
        )
        self._row(parent, 4, "Controller Backend", self.controller_backend_combo)

        serial_frame = ttk.Frame(parent)
        serial_frame.columnconfigure(0, weight=1)
        serial = ttk.Combobox(serial_frame, textvariable=self.vars["serialPort"], values=list_serial_ports())
        self.serial_combo = serial
        serial.grid(row=0, column=0, sticky="ew")
        ttk.Button(serial_frame, text="Refresh", command=self.refresh_ports).grid(row=0, column=1, padx=(8, 0))
        self._row(parent, 5, "Serial Port", serial_frame)

        self._row(parent, 6, "Controller Slot", ttk.Entry(parent, textvariable=self.vars["controllerSlot"]))
        ttk.Checkbutton(parent, text="Bind input to projector focus", variable=self.vars["bindToProjectorFocus"]).grid(
            row=7, column=1, sticky="w", pady=6
        )

        inactive = ttk.Combobox(parent, textvariable=self.vars["inactiveAction"], values=("home", "neutral", "none"), state="readonly")
        self._row(parent, 8, "When Inactive", inactive)
        disconnect = ttk.Combobox(parent, textvariable=self.vars["disconnectAction"], values=("home", "neutral", "none"), state="readonly")
        self._row(parent, 9, "On Disconnect", disconnect)
        self._row(parent, 10, "Home Duration", ttk.Entry(parent, textvariable=self.vars["homeDuration"]))
        self._row(parent, 11, "Home Cooldown", ttk.Entry(parent, textvariable=self.vars["homeCooldown"]))

        ttk.Checkbutton(parent, text="Debug bridge output", variable=self.vars["debugBridge"]).grid(row=12, column=1, sticky="w", pady=6)
        socket_frame = ttk.Frame(parent)
        socket_frame.columnconfigure(0, weight=1)
        self.socket_host_combo = ttk.Combobox(socket_frame, textvariable=self.vars["socketHost"])
        self.socket_host_combo.grid(row=0, column=0, sticky="ew")
        ttk.Button(socket_frame, text="Adapters", command=self.refresh_bind_addresses).grid(row=0, column=1, padx=(8, 0))
        self._row(parent, 13, "Socket Bind", socket_frame)
        self._row(parent, 14, "Socket Port", ttk.Entry(parent, textvariable=self.vars["socketPort"]))
        self._row(parent, 15, "Socket Status File", self._entry_with_browse(parent, "socketStatusFile", "Select socket status file"))
        self._row(parent, 16, "Exit Signal File", self._entry_with_browse(parent, "sessionExitSignalFile", "Select session exit signal file"))

        for index in range(2):
            parent.columnconfigure(index, weight=1 if index == 1 else 0)

    def _build_tools_tab(self, parent):
        actions = ttk.Frame(parent)
        actions.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        actions.columnconfigure(4, weight=1)
        ttk.Button(actions, text="Run Diagnostics", command=self.run_diagnostics).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(actions, text="Start Bridge", command=self.start_bridge).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(actions, text="Stop Bridge", command=self.stop_bridge).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(actions, text="Clear", command=lambda: self.output.delete("1.0", "end")).grid(row=0, column=3)

        self.output = ScrolledText(parent, height=24, wrap="word", font=("Consolas", 10))
        self.output.grid(row=1, column=0, sticky="nsew")

    def _build_discord_tab(self, parent):
        ttk.Label(parent, text="Socket Status").grid(row=0, column=0, sticky="w", padx=(0, 12), pady=(0, 8))
        self.socket_status_var = tk.StringVar(value="Socket bridge is not reporting status yet.")
        ttk.Label(parent, textvariable=self.socket_status_var).grid(row=0, column=1, sticky="ew", pady=(0, 8))

        bind_box = ttk.LabelFrame(parent, text="Bind Address", style="Panel.TLabelframe")
        bind_box.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        bind_box.columnconfigure(0, weight=1)
        self.bind_list = tk.Listbox(bind_box, height=6, exportselection=False)
        self.bind_list.grid(row=0, column=0, columnspan=3, sticky="ew")
        ttk.Button(bind_box, text="Refresh Adapters", command=self.refresh_bind_addresses).grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Button(bind_box, text="Use Selected", command=self.use_selected_bind_address).grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        ttk.Button(bind_box, text="Sync Discord Relay", command=self.sync_discord_relay).grid(row=1, column=2, sticky="e", padx=(8, 0), pady=(8, 0))

        discord_box = ttk.LabelFrame(parent, text="Local Discord Connector", style="Panel.TLabelframe")
        discord_box.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        discord_box.columnconfigure(2, weight=1)
        ttk.Button(discord_box, text="Start Discord Bot", command=self.start_discord_bot).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(discord_box, text="Stop Discord Bot", command=self.stop_discord_bot).grid(row=0, column=1, padx=(0, 8))
        self.discord_status_var = tk.StringVar(value="Discord bot is stopped.")
        ttk.Label(discord_box, textvariable=self.discord_status_var).grid(row=0, column=2, sticky="w")

        ttk.Label(parent, text="Use 127.0.0.1 when the Discord bot runs on this PC. Use a specific LAN adapter IP when the bot runs elsewhere on your network.").grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(0, 8)
        )
        self.refresh_bind_addresses()

    def _row(self, parent, row, label, widget):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=5)
        widget.grid(row=row, column=1, sticky="ew", pady=5)

    def _entry_with_browse(self, parent, key, title):
        frame = ttk.Frame(parent)
        frame.columnconfigure(0, weight=1)
        ttk.Entry(frame, textvariable=self.vars[key]).grid(row=0, column=0, sticky="ew")
        ttk.Button(frame, text="Browse", command=lambda: self.browse_file(key, title)).grid(row=0, column=1, padx=(8, 0))
        return frame

    def _folder_with_browse(self, parent, key):
        frame = ttk.Frame(parent)
        frame.columnconfigure(0, weight=1)
        ttk.Entry(frame, textvariable=self.vars[key]).grid(row=0, column=0, sticky="ew")
        ttk.Button(frame, text="Browse", command=lambda: self.browse_folder(key)).grid(row=0, column=1, padx=(8, 0))
        return frame

    def browse_file(self, key, title):
        selected = filedialog.askopenfilename(
            title=title,
            filetypes=(("Executable", "*.exe"), ("All files", "*.*")),
        )
        if selected:
            self.vars[key].set(selected)

    def browse_folder(self, key):
        selected = filedialog.askdirectory(title="Select folder")
        if selected:
            self.vars[key].set(selected)

    def refresh_ports(self):
        ports = list_serial_ports()
        self.serial_combo.configure(values=ports)
        if self.vars["serialPort"].get() not in ports and ports:
            self.vars["serialPort"].set(ports[0])

    def refresh_bind_addresses(self):
        self.bind_address_choices = list_bind_addresses()
        labels = [label for label, _ip in self.bind_address_choices]
        if hasattr(self, "socket_host_combo"):
            self.socket_host_combo.configure(values=[ip for _label, ip in self.bind_address_choices])
        if hasattr(self, "bind_list"):
            self.bind_list.delete(0, "end")
            current = self.vars["socketHost"].get()
            selected_index = 0
            for index, (label, ip) in enumerate(self.bind_address_choices):
                self.bind_list.insert("end", label)
                if ip == current:
                    selected_index = index
            if labels:
                self.bind_list.selection_set(selected_index)
                self.bind_list.see(selected_index)

    def use_selected_bind_address(self):
        if not hasattr(self, "bind_list"):
            return
        selection = self.bind_list.curselection()
        if not selection:
            return
        _label, ip = self.bind_address_choices[selection[0]]
        self.vars["socketHost"].set(ip)
        self._write_output(f"Socket bind address set to {ip}\n")

    def sync_discord_relay(self):
        try:
            settings = self.collect_settings()
            update_env_file(
                DISCORD_ENV_PATH,
                {
                    "DISCORD_RELAY_HOST": settings["socketHost"],
                    "DISCORD_RELAY_PORT": str(settings["socketPort"]),
                },
            )
        except Exception as exc:
            messagebox.showerror("Discord", f"Unable to update Discord .env:\n{exc}")
            return
        self._write_output(f"Updated Discord relay target in {DISCORD_ENV_PATH}\n")

    def reload_settings(self):
        settings = load_settings()
        for key, value in settings.items():
            if key not in self.vars:
                continue
            var = self.vars[key]
            if isinstance(var, tk.BooleanVar):
                var.set(bool(value))
            else:
                var.set("" if value is None else str(value))
        self._sync_mode_state()
        self._write_output(f"Loaded settings from {CONFIG_PATH}\n")

    def collect_settings(self):
        settings = dict(DEFAULT_SETTINGS)
        settings["pythonExe"] = self.vars["pythonExe"].get().strip()
        settings["obsDir"] = self.vars["obsDir"].get().strip()
        settings["obsExe"] = self.vars["obsExe"].get().strip()
        settings["projectorTitle"] = self.vars["projectorTitle"].get().strip() or "Projector"
        settings["mode"] = self.vars["mode"].get()
        settings["controllerBackend"] = self.vars["controllerBackend"].get()
        settings["serialPort"] = self.vars["serialPort"].get().strip()
        slot = self.vars["controllerSlot"].get().strip()
        settings["controllerSlot"] = None if slot == "" else int(slot)
        settings["bindToProjectorFocus"] = bool(self.vars["bindToProjectorFocus"].get())
        settings["inactiveAction"] = self.vars["inactiveAction"].get()
        settings["disconnectAction"] = self.vars["disconnectAction"].get()
        settings["homeDuration"] = float(self.vars["homeDuration"].get())
        settings["homeCooldown"] = float(self.vars["homeCooldown"].get())
        settings["debugBridge"] = bool(self.vars["debugBridge"].get())
        settings["socketHost"] = self.vars["socketHost"].get().strip() or "127.0.0.1"
        settings["socketPort"] = int(self.vars["socketPort"].get())
        settings["socketStatusFile"] = self.vars["socketStatusFile"].get().strip() or str(DEFAULT_SOCKET_STATUS_FILE)
        settings["sessionExitSignalFile"] = self.vars["sessionExitSignalFile"].get().strip() or str(DEFAULT_SESSION_EXIT_SIGNAL_FILE)
        return settings

    def save_current(self):
        try:
            settings = self.collect_settings()
            save_settings(settings)
        except ValueError as exc:
            messagebox.showerror("Settings", f"Invalid numeric value:\n{exc}")
            return False
        except OSError as exc:
            messagebox.showerror("Settings", f"Unable to save settings:\n{exc}")
            return False
        self._write_output(f"Saved settings to {CONFIG_PATH}\n")
        return True

    def _sync_mode_state(self):
        mode = self.vars["mode"].get()
        controller_state = "readonly" if mode in ("controller", "keyboard") else "disabled"
        if hasattr(self, "controller_backend_combo"):
            self.controller_backend_combo.configure(state=controller_state)

    def build_bridge_command(self, diagnose=False):
        settings = self.collect_settings()
        python = settings["pythonExe"]
        mode = settings["mode"]
        backend = "socket" if mode == "socket" else settings["controllerBackend"]
        log_name = "xinput2serial-gui-diagnose.log" if diagnose else "xinput2serial-gui.log"
        command = [
            python,
            str(BRIDGE_SCRIPT),
            "--auto",
            "--backend",
            backend,
            "--startup-debug",
            "--log-file",
            str(PLAYNITE_LOG_DIR / log_name),
        ]
        if diagnose:
            command.append("--diagnose")
            return command
        if settings["bindToProjectorFocus"]:
            command.extend(["--window", settings["projectorTitle"], "--inactive-action", settings["inactiveAction"]])
        else:
            command.extend(["--inactive-action", "neutral"])
        command.extend(
            [
                "--disconnect-action",
                settings["disconnectAction"],
                "--home-duration",
                str(settings["homeDuration"]),
                "--home-cooldown",
                str(settings["homeCooldown"]),
            ]
        )
        if mode == "keyboard":
            command.append("--keyboard")
        if mode == "socket":
            command.extend(
                [
                    "--socket-host",
                    settings["socketHost"],
                    "--socket-port",
                    str(settings["socketPort"]),
                    "--socket-status-file",
                    settings["socketStatusFile"],
                ]
            )
        if settings["debugBridge"]:
            command.append("--debug")
        if settings["serialPort"]:
            command.extend(["--port", settings["serialPort"]])
        if mode != "socket" and settings["controllerSlot"] is not None:
            command.extend(["--controller", str(settings["controllerSlot"])])
        return command

    def run_diagnostics(self):
        if not self.save_current():
            return
        command = self.build_bridge_command(diagnose=True)
        self._write_output("\n> " + subprocess.list2cmdline(command) + "\n")
        self._run_command(command)

    def start_bridge(self):
        if self.bridge_process and self.bridge_process.poll() is None:
            messagebox.showinfo("Bridge", "The manual bridge is already running.")
            return
        if not self.save_current():
            return
        command = self.build_bridge_command(diagnose=False)
        self._write_output("\n> " + subprocess.list2cmdline(command) + "\n")
        try:
            self.bridge_process = subprocess.Popen(
                command,
                cwd=str(ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError as exc:
            messagebox.showerror("Bridge", f"Unable to start bridge:\n{exc}")
            return
        threading.Thread(target=self._read_process, args=(self.bridge_process, "Bridge"), daemon=True).start()

    def stop_bridge(self):
        if not self.bridge_process or self.bridge_process.poll() is not None:
            self._write_output("Manual bridge is not running.\n")
            return
        self.bridge_process.terminate()
        self._write_output("Stopping manual bridge...\n")

    def start_discord_bot(self):
        if self.discord_process and self.discord_process.poll() is None:
            messagebox.showinfo("Discord", "The Discord bot is already running.")
            return
        if not DISCORD_ENV_PATH.exists():
            messagebox.showwarning("Discord", f"Discord .env was not found:\n{DISCORD_ENV_PATH}")
        try:
            settings = self.collect_settings()
        except ValueError as exc:
            messagebox.showerror("Settings", f"Invalid numeric value:\n{exc}")
            return
        command = [settings["pythonExe"], str(DISCORD_BOT_SCRIPT)]
        self._write_output("\n> " + subprocess.list2cmdline(command) + "\n")
        try:
            self.discord_process = subprocess.Popen(
                command,
                cwd=str(ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError as exc:
            messagebox.showerror("Discord", f"Unable to start Discord bot:\n{exc}")
            return
        self.discord_status_var.set("Discord bot is running.")
        threading.Thread(target=self._read_process, args=(self.discord_process, "Discord bot"), daemon=True).start()

    def stop_discord_bot(self):
        if not self.discord_process or self.discord_process.poll() is not None:
            self.discord_status_var.set("Discord bot is stopped.")
            self._write_output("Discord bot is not running.\n")
            return
        self.discord_process.terminate()
        self.discord_status_var.set("Stopping Discord bot...")
        self._write_output("Stopping Discord bot...\n")

    def on_close(self):
        if self.bridge_process and self.bridge_process.poll() is None:
            self.bridge_process.terminate()
        if self.discord_process and self.discord_process.poll() is None:
            self.discord_process.terminate()
        self.destroy()

    def _run_command(self, command):
        def worker():
            try:
                result = subprocess.run(
                    command,
                    cwd=str(ROOT),
                    text=True,
                    capture_output=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    timeout=30,
                )
                if result.stdout:
                    self.output_queue.put(result.stdout)
                if result.stderr:
                    self.output_queue.put(result.stderr)
                self.output_queue.put(f"Exit code: {result.returncode}\n")
            except Exception as exc:
                self.output_queue.put(f"Command failed: {exc}\n")

        threading.Thread(target=worker, daemon=True).start()

    def _read_process(self, process, label):
        if process.stdout:
            for line in process.stdout:
                self.output_queue.put(line)
        code = process.wait()
        self.output_queue.put(f"{label} exited with code {code}\n")
        if label == "Discord bot":
            self.output_queue.put(("__DISCORD_STATUS__", "Discord bot is stopped."))

    def _write_output(self, text):
        self.output.insert("end", text)
        self.output.see("end")

    def _drain_output(self):
        try:
            while True:
                item = self.output_queue.get_nowait()
                if isinstance(item, tuple) and item[0] == "__DISCORD_STATUS__":
                    self.discord_status_var.set(item[1])
                else:
                    self._write_output(item)
        except queue.Empty:
            pass
        self.after(100, self._drain_output)

    def _poll_socket_status(self):
        try:
            path = Path(self.vars["socketStatusFile"].get() or DEFAULT_SOCKET_STATUS_FILE)
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                text = (
                    f"{data.get('state', 'unknown')} on {data.get('host')}:{data.get('port')} | "
                    f"active peers: {data.get('activePeers', 0)} | "
                    f"last peer: {data.get('lastPeer') or 'none'} | "
                    f"last event: {data.get('lastEvent') or 'none'}"
                )
            else:
                text = "Socket bridge is not reporting status yet."
            if hasattr(self, "socket_status_var"):
                self.socket_status_var.set(text)
        except Exception as exc:
            if hasattr(self, "socket_status_var"):
                self.socket_status_var.set(f"Socket status unavailable: {exc}")
        self.after(1000, self._poll_socket_status)


if __name__ == "__main__":
    app = SwitchAutomationGui()
    app.mainloop()
