## Helper Scripts

**Included Files**

- `PlaynitePreStart.ps1`: Recommended Playnite `Pre` event script. Starts OBS and records session state.
- `PlaynitePostStart.ps1`: Recommended Playnite `Post` event script. Opens the OBS projector and starts xinput2serial in the background.
- `PlayniteExit.ps1`: Recommended Playnite `Exit` event script. Stops xinput2serial and closes OBS only if the session started it.
- `PlayniteSessionHost.ps1`: Recommended Playnite emulator `General` target. Gives Playnite a process to track until the projector closes.
- `Launch Switch.cmd`: Recommended Playnite entrypoint. This keeps Playnite pointed at one stable file.
- `switch_launcher.py`: Single Python launcher that starts OBS, opens the projector, runs xinput2serial, monitors the projector window, and cleans up.
- `SwitchWrapper.ps1`: PowerShell wrapper to launch OBS, start the projector, and run xinput2serial with monitoring and cleanup.
- `start_obs_fullscreen.py`: Python script to open the OBS projector window via WebSocket.

### Recommended Playnite Setup

Use Playnite's built-in game event scripts instead of launching the long-running wrapper directly.

In Playnite, edit the Switch game entry, open the `Scripts` tab, and configure:

- `Pre`: paste the contents of `PlaynitePreStart.ps1`
- `Post`: paste the contents of `PlaynitePostStart.ps1`
- `Exit`: paste the contents of `PlayniteExit.ps1`

In the emulator profile `General` tab, configure:

```text
Executable:
powershell.exe

Arguments:
-NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\Nintendo Automation\xInput-Switch\Playnite Launcher Scripts\PlayniteSessionHost.ps1"

Working Directory:
C:\Nintendo Automation\xInput-Switch\Playnite Launcher Scripts

Tracking Mode:
Original process
```

This follows Playnite's scripting model: scripts run synchronously, so each script should do short lifecycle work and then return. The input bridge runs as a background process and Playnite's `Exit` event performs cleanup.

The old launcher command is no longer recommended:

```powershell
-NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\Nintendo Automation\xInput-Switch\Playnite Launcher Scripts\SwitchWrapper.ps1"
```

If you prefer to keep the Playnite script boxes tiny, each script box can call the file instead:

```text
& "C:\Nintendo Automation\xInput-Switch\Playnite Launcher Scripts\PlaynitePreStart.ps1"
& "C:\Nintendo Automation\xInput-Switch\Playnite Launcher Scripts\PlaynitePostStart.ps1"
& "C:\Nintendo Automation\xInput-Switch\Playnite Launcher Scripts\PlayniteExit.ps1"
```

Use the matching line in the matching Playnite event box. Pasting the full script contents is more self-contained; calling the files is easier to update later.

#### Configuration

Most settings are near the top of `PlaynitePostStart.ps1`:

```powershell
$projectorTitle = "Windowed Projector (Source) - Scene"
$useKeyboardMouse = $false
$debugBridge = $true
$serialPort = "COM3"
$controllerSlot = 0
$bindToProjectorFocus = $true
```

Set explicit hardware options like this if auto-detection is unreliable:

```powershell
$serialPort = "COM3"
$controllerSlot = 0
```

`$bindToProjectorFocus` controls whether input is only streamed while the OBS projector window is focused. When it is `true`, focus loss sends a short HOME press to the Switch, then neutral packets until the projector is focused again.

Use keyboard/mouse mode instead of an Xbox/XInput controller:

```powershell
$useKeyboardMouse = $true
```

The Playnite launcher starts the bridge with `--backend auto`, which tries XInput first and then pygame/SDL for Sunshine `Auto` devices such as DS4.

Logs are written to:

```text
C:\Nintendo Automation\xInput-Switch\Playnite Launcher Scripts\playnite-switch-session.log
C:\Nintendo Automation\xInput-Switch\Playnite Launcher Scripts\xinput2serial.log
```

To test what the bridge can see without launching Playnite:

```powershell
py -3 "C:\Nintendo Automation\xInput-Switch\xInput2Serial\xinput2serial.py" --diagnose --log-file "C:\Nintendo Automation\xInput-Switch\Playnite Launcher Scripts\xinput2serial-diagnose.log"
```

The bridge needs two separate pieces:

- A serial adapter / firmware board connected to the PC and Switch dock. This should appear as a COM port, usually `USB-SERIAL CH340`.
- A controller input source visible to Windows as XInput, usually an Xbox-compatible controller connected to the PC. If no XInput controller appears in diagnostics, controller mode cannot stream inputs even if the dock-side board is connected.

### Alternative Single-File Launcher

`Launch Switch.cmd` and `switch_launcher.py` are kept as an alternative for non-Playnite launchers or for testing outside Playnite. For Playnite itself, prefer the `Pre` / `Post` / `Exit` scripts above.

### PowerShell Script

**Overview**

The PowerShell script (`SwitchWrapper.ps1`) automates launching OBS, invoking the Python projector script, and running the xinput2serial input script, with built-in monitoring and cleanup.

**Usage**

Starting the Script:

```powershell
.\SwitchWrapper.ps1 -ProjectorTitle "Your Desired Projector Window Title"
```

Replace `SwitchWrapper.ps1` with the name of your PowerShell script file and `"Your Desired Projector Window Title"` with the actual title of the projector window you want to monitor.

**Parameters**

- `-ProjectorTitle`: Specifies the title of the projector window to monitor for xinput2serial.

**Script Structure**

1. OBS Startup: Checks if OBS is running; if not, starts OBS.
2. Projector Activation: Executes the Python script to open the OBS projector.
3. xinput2serial Launch: Starts the xinput2serial Python script bound to the projector window.
4. Monitoring: Waits for the projector window to appear, then monitors it until closure.
5. Cleanup: Stops xinput2serial and gracefully shuts down OBS.

**Logging**

The script logs all significant events and process IDs to a log file specified within the script.

### Python Script

**Overview**

The Python script is generally used to control aspects of OBS, such as switching to fullscreen mode. This script is executed by the PowerShell script during the setup phase.

**Usage**

The Python script should be configured according to your specific automation needs for OBS. Ensure that the Python environment and required libraries are correctly set up.

**Dependencies**

The Python script requires the installation of `obs-websocket` library. You can install it from [here](https://github.com/obsproject/obs-websocket).

**Notes**

- Ensure that all paths in the scripts (e.g., to OBS, Python, and the Java application) are correctly set according to your system's configuration.
- The PowerShell script should be run with appropriate permissions to start and stop processes on the system.
- For automated use, consider adding these scripts to your startup applications or scheduled tasks for seamless execution.
