<#
.SYNOPSIS
    Reliable wrapper for managing OBS Fullscreen Projector and xinput2serial via Playnite.
.DESCRIPTION
    Starts OBS and the fullscreen projector, then runs xinput2serial.
    Reliably detects and monitors projector window status using native PowerShell.
#>

param(
    [string]$ObsDir          = "C:\Program Files\obs-studio\bin\64bit",
    [string]$PythonExe       = "python.exe",
    [string]$BaseDir         = "C:\Nintendo Automation\xInput-Switch",
    [string]$ProjectorWS     = (Join-Path $BaseDir "Playnite Launcher Scripts\start_obs_fullscreen.py"),
    [string]$XInputScript    = (Join-Path $BaseDir "xInput2Serial\xinput2serial.py"),
    [string]$ProjectorTitle  = "Windowed Projector (Source) - Scene",
    [int]$ProjectorAppearTimeoutSeconds = 25,
    [int]$XInputStartupGraceSeconds = 3
)

$ObsExe    = Join-Path $ObsDir "obs64.exe"
$ObsWorkDir = $ObsDir
$startedObsByWrapper = $false
$obsProc = $null
$xiProc = $null

function Log-Message($msg) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[Wrapper][$timestamp] $msg"
}

function Get-ProjectorProcess([string]$title) {
    Get-Process -ErrorAction SilentlyContinue | Where-Object {
        $_.MainWindowTitle -like "*$title*"
    }
}

function Stop-ProcessSafe($proc, [string]$name) {
    if ($null -eq $proc) {
        return
    }

    $running = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
    if ($running) {
        Log-Message "Stopping $name (PID $($proc.Id))..."
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
}

try {
    # 1. Start OBS
    if (!(Get-Process -Name obs64 -ErrorAction SilentlyContinue)) {
        Log-Message "Starting OBS with disable-shutdown-check..."
        try {
            $obsProc = Start-Process -FilePath $ObsExe -WorkingDirectory $ObsWorkDir -ArgumentList "--disable-shutdown-check" -PassThru
            $startedObsByWrapper = $true
        }
        catch {
            throw "Failed to launch OBS ($ObsExe): $($_.Exception.Message)"
        }

        Start-Sleep -Seconds 3
        Log-Message "OBS started (PID $($obsProc.Id))."
    }
    else {
        Log-Message "OBS is already running; wrapper will not shut it down on exit."
    }

    # 2. Start projector helper and require success
    Log-Message "Starting projector helper..."
    $projectorProc = Start-Process -FilePath $PythonExe -ArgumentList "`"$ProjectorWS`"" -PassThru -Wait
    if ($projectorProc.ExitCode -ne 0) {
        throw "Projector helper exited with code $($projectorProc.ExitCode)."
    }

    # 3. Wait for projector window to appear
    Log-Message "Waiting for projector window '$ProjectorTitle' to appear..."
    $windowDeadline = (Get-Date).AddSeconds($ProjectorAppearTimeoutSeconds)
    while ((Get-Date) -lt $windowDeadline -and !(Get-ProjectorProcess -title $ProjectorTitle)) {
        Start-Sleep -Milliseconds 500
    }

    if (!(Get-ProjectorProcess -title $ProjectorTitle)) {
        throw "Projector window '$ProjectorTitle' did not appear within $ProjectorAppearTimeoutSeconds seconds."
    }
    Log-Message "Projector window detected."

    # 4. Start xinput2serial and verify it stays alive past startup grace
    Log-Message "Launching xinput2serial bound to '$ProjectorTitle'..."
    $xiProc = Start-Process -FilePath $PythonExe -ArgumentList "`"$XInputScript`" --auto --window `"$ProjectorTitle`"" -PassThru
    Start-Sleep -Seconds $XInputStartupGraceSeconds

    if ($xiProc.HasExited) {
        throw "xinput2serial exited early with code $($xiProc.ExitCode)."
    }

    Log-Message "xinput2serial is running (PID $($xiProc.Id)). Monitoring projector lifecycle..."
    while ($true) {
        if ($xiProc.HasExited) {
            throw "xinput2serial exited during monitoring with code $($xiProc.ExitCode)."
        }

        if (!(Get-ProjectorProcess -title $ProjectorTitle)) {
            Log-Message "Projector window closed. Ending wrapper session."
            break
        }

        Start-Sleep -Seconds 1
    }

    exit 0
}
catch {
    Log-Message "ERROR: $($_.Exception.Message)"
    exit 1
}
finally {
    # 5. Cleanup xinput2serial
    Stop-ProcessSafe -proc $xiProc -name "xinput2serial"

    # Gracefully close OBS only if wrapper started it
    if ($startedObsByWrapper) {
        $ownedObs = $null
        if ($obsProc -and !$obsProc.HasExited) {
            $ownedObs = Get-Process -Id $obsProc.Id -ErrorAction SilentlyContinue
        }
        if ($ownedObs) {
            Log-Message "Attempting graceful shutdown of OBS (PID $($ownedObs.Id))..."
            $ownedObs.CloseMainWindow() | Out-Null
            Start-Sleep -Seconds 5
            $ownedObs = Get-Process -Id $ownedObs.Id -ErrorAction SilentlyContinue
            if ($ownedObs) {
                Log-Message "Forcing OBS shutdown..."
                Stop-Process -Id $ownedObs.Id -Force -ErrorAction SilentlyContinue
            }
            else {
                Log-Message "OBS exited gracefully."
            }
        }
        else {
            Log-Message "OBS already exited."
        }
    }
    else {
        Log-Message "Leaving pre-existing OBS process running."
    }

    Log-Message "Wrapper cleanup completed."
}
