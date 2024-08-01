## Helper Scripts

### PowerShell Script

**Overview**

The PowerShell script is used by Playnite during game launch to automate the setup and execution of the Java application, OBS, and Python scripts. It handles starting the necessary software, passing parameters, and monitoring processes. To implement, add it to a custom emulator defined in Playnite.

**Usage**

Starting the Script:

```powershell
.\YourScriptName.ps1 -windowTitle "Your Desired Window Title"
```

Replace `YourScriptName.ps1` with the name of your PowerShell script file and `"Your Desired Window Title"` with the actual title of the window you want to monitor.

**Parameters**

- `-windowTitle`: Specifies the title of the window that the Java application should monitor for activity.

**Script Structure**

1. OBS Startup: Checks if OBS is running; if not, it starts OBS and logs the process ID.
2. Python Script Execution: Executes a Python script, typically used to automate other tasks, such as setting OBS to fullscreen.
3. Java Application Launch: Starts the Java application with specified arguments, including headless mode and window title.
4. Monitoring: Continuously monitors the OBS process, ensuring that the Java application and other processes are terminated if OBS is closed.

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