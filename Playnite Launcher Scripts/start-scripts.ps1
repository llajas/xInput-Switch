param (
    [string]$windowTitle = "Windowed Projector (Source) - Scene" # Default value
)

# Path to the base directory of the project
$basePath = "C:\Users\user\xInput-Switch"

# Path to OBS executable
$obsPath = "C:\Program Files\obs-studio\bin\64bit\obs64.exe"
$obsWorkingDirectory = "C:\Program Files\obs-studio\bin\64bit"

# Path to Python executable
$pythonPath = "C:\Python312\python.exe"

# Path to the Python script
$pythonScriptPath = "$basePath\Playnite Launcher Scripts\start_obs_fullscreen.py"

# Path to Java executable
$javaPath = "C:\Program Files\Eclipse Adoptium\jre-17.0.12.7-hotspot\bin\javaw.exe"  # Use javaw.exe to avoid spawning a shell window

# Path to the Java JAR file
$jarPath = "$basePath\xInput2Serial\target\xinput-serial-1.0-SNAPSHOT.jar"

# Function to log messages
function Log-Message {
    param (
        [string]$message
    )
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logMessage = "[$timestamp] $message"
    Write-Host $logMessage
    Add-Content -Path $logFile -Value $logMessage
}

# Path to the log file
$logFile = "$basePath\xInput-Switch\Playnite Launcher Scripts\start-scripts.log"

# Path to the process ID file
$processIdFile = "$basePath\xInput-Switch\Playnite Launcher Scripts\java-process-id.log"

# Ensure the log file exists
if (-Not (Test-Path $logFile)) {
    New-Item -Path $logFile -ItemType File -Force | Out-Null
}

# Clear the log file at the start
Clear-Content -Path $logFile

# Ensure the process ID file exists
if (-Not (Test-Path $processIdFile)) {
    New-Item -Path $processIdFile -ItemType File -Force | Out-Null
}

# Clear the process ID file at the start
Clear-Content -Path $processIdFile

# Function to check if OBS is running
function Is-OBSRunning {
    Get-Process -Name "obs64" -ErrorAction SilentlyContinue
}

# Start OBS if not already running
if (-not (Is-OBSRunning)) {
    # Verify if the OBS executable exists
    if (Test-Path $obsPath) {
        # Log and run OBS
        Log-Message "Starting OBS..."
        $obsProcess = Start-Process -FilePath $obsPath -WorkingDirectory $obsWorkingDirectory -PassThru
        Log-Message "OBS started with Process ID: $($obsProcess.Id)."
    } else {
        Log-Message "The OBS executable was not found: $obsPath"
    }
} else {
    Log-Message "OBS is already running."
}

# Verify if the Python executable exists
if (Test-Path $pythonPath) {
    # Verify if the Python script exists
    if (Test-Path $pythonScriptPath) {
        # Log and run the Python script
        Log-Message "Starting Python script..."
        $pythonProcess = Start-Process -FilePath $pythonPath -ArgumentList $pythonScriptPath -PassThru
        Log-Message "Python script started with Process ID: $($pythonProcess.Id)."
    } else {
        Log-Message "The Python script file was not found: $pythonScriptPath"
    }
} else {
    Log-Message "The Python executable was not found: $pythonPath"
}

# Verify if the Java executable exists
if (Test-Path $javaPath) {
    # Log and run the Java JAR file in headless and auto mode with window title
    Log-Message "Starting Java JAR file..."
    $javaProcess = Start-Process -FilePath $javaPath -ArgumentList "-jar `"$jarPath`" --headless --auto --window `"$windowTitle`"" -NoNewWindow -PassThru
    Log-Message "Java JAR file started with Process ID: $($javaProcess.Id)."
    Add-Content -Path $processIdFile -Value $javaProcess.Id
} else {
    Log-Message "The Java executable was not found: $javaPath"
}

# Monitor the OBS process
Log-Message "Monitoring OBS process..."
while ($true) {
    Start-Sleep -Seconds 1

    # Check if the OBS process is running
    if (-not (Is-OBSRunning)) {
        Log-Message "OBS process is not running. Terminating Java process."

        # Terminate the Java process
        if ($null -ne $javaProcess -and -not $javaProcess.HasExited) {
            $javaProcess.Kill()
            Log-Message "Java process with ID $($javaProcess.Id) has been terminated."
        }

        # Terminate the Python process (if necessary)
        if ($null -ne $pythonProcess -and -not $pythonProcess.HasExited) {
            $pythonProcess.Kill()
            Log-Message "Python process with ID $($pythonProcess.Id) has been terminated."
        }

        break
    }
}

Log-Message "Script finished."
