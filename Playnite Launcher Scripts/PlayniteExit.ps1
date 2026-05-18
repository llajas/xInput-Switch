<# Playnite "Exit" script.
   Stops xinput2serial after the game stops and closes OBS only if this
   Playnite session started OBS. #>

$ErrorActionPreference = "Continue"

$baseDir = "C:\Nintendo Automation\xInput-Switch"
$logFile = Join-Path $baseDir "Playnite Launcher Scripts\playnite-switch-session.log"
$bridgePidFile = Join-Path $baseDir "Playnite Launcher Scripts\xinput2serial.pid"
$forceCloseObs = $false
if ($global:SwitchAutomation -and $global:SwitchAutomation.LogFile) {
    $logFile = $global:SwitchAutomation.LogFile
}

function Write-SwitchLog {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $logFile -Value $line
}

function Stop-ProcessById {
    param(
        [Nullable[int]]$ProcessId,
        [string]$Name
    )

    if ($null -eq $ProcessId) {
        return
    }

    $proc = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if (-not $proc) {
        Write-SwitchLog "$Name PID $ProcessId is no longer running."
        return
    }

    Write-SwitchLog "Stopping $Name PID $ProcessId."
    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
}

function Stop-XInputBridgeProcesses {
    $pattern = [regex]::Escape("C:\Nintendo Automation\xInput-Switch\xInput2Serial\xinput2serial.py")
    $matches = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match $pattern }

    foreach ($match in $matches) {
        Write-SwitchLog "Stopping lingering xinput2serial process PID $($match.ProcessId)."
        Stop-Process -Id $match.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

if ($global:SwitchAutomation) {
    Stop-ProcessById -ProcessId $global:SwitchAutomation.XInputProcessId -Name "xinput2serial"
} elseif (Test-Path -LiteralPath $bridgePidFile) {
    $pidText = Get-Content -Path $bridgePidFile -ErrorAction SilentlyContinue | Select-Object -First 1
    $parsedPid = 0
    if ([int]::TryParse($pidText, [ref]$parsedPid)) {
        Stop-ProcessById -ProcessId $parsedPid -Name "xinput2serial"
    }
}

Stop-XInputBridgeProcesses

if ($global:SwitchAutomation) {
    if ($global:SwitchAutomation.ObsStartedByPlaynite -and $global:SwitchAutomation.ObsProcessId) {
        $obsProc = Get-Process -Id $global:SwitchAutomation.ObsProcessId -ErrorAction SilentlyContinue
        if ($obsProc) {
            Write-SwitchLog "Closing OBS PID $($obsProc.Id)."
            $obsProc.CloseMainWindow() | Out-Null
            Start-Sleep -Seconds 15
            if (-not $obsProc.HasExited) {
                if ($forceCloseObs) {
                    Write-SwitchLog "OBS did not close in time; forcing shutdown."
                    Stop-Process -Id $obsProc.Id -Force -ErrorAction SilentlyContinue
                } else {
                    Write-SwitchLog "OBS did not close in time; leaving it open to avoid unsafe shutdown prompt."
                }
            }
        }
    } else {
        Write-SwitchLog "Leaving OBS open because this Playnite session did not start it."
    }

    $global:SwitchAutomation = $null
} else {
    Write-SwitchLog "No SwitchAutomation session state was found during Exit."
}

Remove-Item -LiteralPath $bridgePidFile -Force -ErrorAction SilentlyContinue
Write-SwitchLog "Playnite Switch cleanup completed."
