#!/usr/bin/env python3
import asyncio
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import socket
import time

try:
    import discord
except ImportError:
    raise SystemExit(
        "discord.py is not installed. Run: py -3 -m pip install -r discord_input\\requirements.txt"
    )


ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"


COMMAND_ALIASES = {
    "a": "a",
    "b": "b",
    "x": "x",
    "y": "y",
    "up": "up",
    "u": "up",
    "down": "down",
    "d": "down",
    "left": "left",
    "l": "left",
    "right": "right",
    "r": "right",
    "l1": "l",
    "lb": "l",
    "r1": "r",
    "rb": "r",
    "zl": "zl",
    "lt": "zl",
    "zr": "zr",
    "rt": "zr",
    "plus": "plus",
    "start": "plus",
    "minus": "minus",
    "select": "minus",
    "home": "home",
    "capture": "capture",
    "screenshot": "capture",
}


@dataclass
class Config:
    token: str
    channel_id: int
    relay_host: str
    relay_port: int
    prefix: str
    duration: float
    cooldown: float
    allowed_user_ids: set[int]
    privileged_user_ids: set[int]
    privileged_commands: set[str]
    audit_log_path: Path


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load_config() -> Config:
    load_env_file(ENV_PATH)
    token = os.environ.get("DISCORD_BOT_TOKEN")
    channel_id = os.environ.get("DISCORD_CHANNEL_ID")
    if not token:
        raise SystemExit("DISCORD_BOT_TOKEN is required.")
    if not channel_id:
        raise SystemExit("DISCORD_CHANNEL_ID is required.")

    allowed = set()
    for item in os.environ.get("DISCORD_ALLOWED_USER_IDS", "").split(","):
        item = item.strip()
        if item:
            allowed.add(int(item))

    privileged = set()
    for item in os.environ.get("DISCORD_PRIVILEGED_USER_IDS", "").split(","):
        item = item.strip()
        if item:
            privileged.add(int(item))

    privileged_commands = {
        item.strip().lower()
        for item in os.environ.get("DISCORD_PRIVILEGED_COMMANDS", "home,capture,screenshot").split(",")
        if item.strip()
    }

    return Config(
        token=token,
        channel_id=int(channel_id),
        relay_host=os.environ.get("DISCORD_RELAY_HOST", "127.0.0.1"),
        relay_port=int(os.environ.get("DISCORD_RELAY_PORT", "8765")),
        prefix=os.environ.get("DISCORD_COMMAND_PREFIX", "").strip(),
        duration=int(os.environ.get("DISCORD_COMMAND_DURATION_MS", "200")) / 1000,
        cooldown=int(os.environ.get("DISCORD_COMMAND_COOLDOWN_MS", "500")) / 1000,
        allowed_user_ids=allowed,
        privileged_user_ids=privileged,
        privileged_commands=privileged_commands,
        audit_log_path=Path(os.environ.get("DISCORD_AUDIT_LOG", ROOT / "discord_input-audit.log")),
    )


def parse_command(content: str, prefix: str) -> dict | None:
    text = content.strip().lower()
    if prefix:
        if not text.startswith(prefix):
            return None
        text = text[len(prefix):].strip()
    if not text:
        return None

    token = text.split()[0]
    command = COMMAND_ALIASES.get(token)
    if not command:
        return None
    return {"command": command, "raw": token}


def send_event(config: Config, event: dict) -> None:
    event = dict(event)
    event.setdefault("duration", config.duration)
    payload = (json.dumps(event, separators=(",", ":")) + "\n").encode("utf-8")
    with socket.create_connection((config.relay_host, config.relay_port), timeout=1.0) as sock:
        sock.sendall(payload)


def append_audit_log(config: Config, message: discord.Message, event: dict, allowed: bool) -> None:
    status = "allowed" if allowed else "denied"
    command = event.get("command", "")
    raw = event.get("raw", command)
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    line = (
        f"{timestamp} privileged_command={command} raw={raw} "
        f"status={status} user_id={message.author.id} "
        f"channel_id={message.channel.id} message_id={message.id}"
    )
    config.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
    with config.audit_log_path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    print(line)


class InputBot(discord.Client):
    def __init__(self, config: Config):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.config = config
        self.last_by_user: dict[int, float] = {}

    async def on_ready(self):
        print(f"Logged in as {self.user}. Listening to channel {self.config.channel_id}.")

    async def on_message(self, message: discord.Message):
        if message.author.bot or message.channel.id != self.config.channel_id:
            return
        if self.config.allowed_user_ids and message.author.id not in self.config.allowed_user_ids:
            return

        event = parse_command(message.content, self.config.prefix)
        if not event:
            return
        command = event.get("command")
        if command in self.config.privileged_commands:
            allowed = message.author.id in self.config.privileged_user_ids
            await asyncio.to_thread(append_audit_log, self.config, message, event, allowed)
            if not allowed:
                return

        now = time.time()
        last = self.last_by_user.get(message.author.id, 0)
        if now - last < self.config.cooldown:
            return
        self.last_by_user[message.author.id] = now

        try:
            await asyncio.to_thread(send_event, self.config, event)
        except OSError as exc:
            print(f"Relay send failed: {exc}")


def main() -> int:
    config = load_config()
    InputBot(config).run(config.token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
