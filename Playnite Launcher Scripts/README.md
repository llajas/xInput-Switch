## Helper Scripts

**Included Files**

- `SwitchWrapper.ps1`: PowerShell wrapper to launch OBS, start the projector, and run xinput2serial with monitoring and cleanup.
- `start_obs_fullscreen.py`: Python script to open the OBS projector window via WebSocket.

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