# Discord Input Adapter

This adapter reads commands from one Discord channel and sends them to the local
`xinput2serial.py --backend socket` bridge.

## Secrets

Do not commit Discord tokens. Put local secrets in `discord_input/.env`, which is
ignored by Git, or set the same values as environment variables.

Start from:

```powershell
Copy-Item "C:\Nintendo Automation\xInput-Switch\discord_input\.env.example" "C:\Nintendo Automation\xInput-Switch\discord_input\.env"
```

Required:

```text
DISCORD_BOT_TOKEN=...
DISCORD_CHANNEL_ID=...
```

Sensitive commands can be restricted to approved Discord user IDs:

```text
DISCORD_PRIVILEGED_USER_IDS=285128170011754496
DISCORD_PRIVILEGED_COMMANDS=home,capture,screenshot
DISCORD_AUDIT_LOG=C:\Nintendo Automation\xInput-Switch\discord_input\discord_input-audit.log
```

With that setting, only those users can send `home`, `capture`, or `screenshot`.
Every privileged-command attempt is logged with the command, allow/deny status,
Discord user ID, channel ID, and message ID.

Install the bot dependency:

```powershell
py -3 -m pip install -r "C:\Nintendo Automation\xInput-Switch\discord_input\requirements.txt"
```

## Manual Test

Start the bridge:

```powershell
py -3 "C:\Nintendo Automation\xInput-Switch\xInput2Serial\xinput2serial.py" --backend socket --port COM3 --startup-debug --log-file "C:\Nintendo Automation\xInput-Switch\Playnite Launcher Scripts\xinput2serial-discord.log"
```

Start the Discord bot:

```powershell
py -3 "C:\Nintendo Automation\xInput-Switch\discord_input\discord_input_bot.py"
```

## Commands

Users can send:

```text
a b x y
up down left right
l r zl zr
plus minus home capture
```

Aliases include `start`, `select`, `screenshot`, `lt`, and `rt`.
