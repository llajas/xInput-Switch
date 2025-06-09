<#
.SYNOPSIS
    Reliable wrapper for managing OBS Fullscreen Projector and xinput2serial via Playnite.
.DESCRIPTION
    Starts OBS and the fullscreen projector, then runs xinput2serial.
    Reliably detects and monitors projector window status using native PowerShell.
#>

param(
    [string]$ObsExe          = "C:\Program Files\obs-studio\bin\64bit\obs64.exe",
    [string]$ObsWorkDir      = "C:\Program Files\obs-studio\bin\64bit",
    [string]$PythonExe       = "python.exe",
    [string]$ProjectorWS     = "C:\Users\laure\OneDrive\Games\Automation\start_obs_fullscreen.py",
    [string]$XInputScript    = "C:\Users\laure\OneDrive\Games\Automation\Nintendo Switch\xinput2serial.py",
    [string]$ProjectorTitle  = "Windowed Projector (Source) - Scene"
)

function Log-Message($msg) {
    Write-Host "[Wrapper] $msg"
}

# 1. Start OBS
if (!(Get-Process -Name obs64 -ErrorAction SilentlyContinue)) {
    Log-Message "Starting OBS with disable-shutdown-check..."
    try {
        # Launch OBS with shutdown check disabled to avoid Safe Mode prompt
        Start-Process -FilePath $ObsExe -WorkingDirectory $ObsWorkDir -ArgumentList "--disable-shutdown-check" -PassThru | Out-Null
        Start-Sleep -Seconds 3
        Log-Message "OBS started."
    } catch {
        Log-Message "Failed to launch OBS with disable-shutdown-check. Exiting."
        exit 1
    }
} else {
    Log-Message "OBS is already running."
}

# 2. Start projector via WS script via WS script
Log-Message "Starting projector..."
Start-Process -FilePath $PythonExe -ArgumentList "`"$ProjectorWS`""
Start-Sleep -Seconds 2

# 3. Start xinput2serial script
Log-Message "Launching xinput2serial bound to '$ProjectorTitle'..."
$xiProc = Start-Process -FilePath $PythonExe -ArgumentList "`"$XInputScript`" --auto --window `"$ProjectorTitle`"" -PassThru

# 4. Robustly monitor window using PowerShell native methods
Log-Message "Waiting for projector window to appear..."
$timeout = 20
while ($timeout -gt 0 -and !(Get-Process | Where-Object { $_.MainWindowTitle -like "*$ProjectorTitle*" })) {
    Start-Sleep -Seconds 1
    $timeout--
}

if ($timeout -eq 0) {
    Log-Message "Projector window never appeared. Cleaning up."
    # 5. Cleanup xinput2serial
    Log-Message "Stopping xinput2serial..."
    if (!$xiProc.HasExited) { Stop-Process -Id $xiProc.Id -Force }
    exit 1
}

Log-Message "Projector window detected. Monitoring for closure..."
while (Get-Process | Where-Object { $_.MainWindowTitle -like "*$ProjectorTitle*" }) {
    Start-Sleep -Seconds 1
}

# 5. Cleanup xinput2serial
Log-Message "Projector closed. Stopping xinput2serial..."
if (!$xiProc.HasExited) { Stop-Process -Id $xiProc.Id -Force }

# Gracefully close OBS
Log-Message "Attempting graceful shutdown of OBS..."
$obsProc = Get-Process -Name obs64 -ErrorAction SilentlyContinue
if ($obsProc) {
    $obsProc.CloseMainWindow() | Out-Null
    Start-Sleep -Seconds 5
    # Force close if still running after grace period
    if (!$obsProc.HasExited) {
        Log-Message "Forcing OBS shutdown..."
        $obsProc | Stop-Process -Force
    } else {
        Log-Message "OBS exited gracefully."
    }
} else {
    Log-Message "OBS was not running."
}

Log-Message "OBS cleanup completed."
exit 0
