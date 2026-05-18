<# Playnite "Exit" script.
   Stops xinput2serial after the game stops and closes OBS only if this
   Playnite session started OBS. #>

$ErrorActionPreference = "Continue"

$baseDir = "C:\Nintendo Automation\xInput-Switch"
$logFile = Join-Path $baseDir "Playnite Launcher Scripts\playnite-switch-session.log"
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

if ($global:SwitchAutomation) {
    Stop-ProcessById -ProcessId $global:SwitchAutomation.XInputProcessId -Name "xinput2serial"

    if ($global:SwitchAutomation.ObsStartedByPlaynite -and $global:SwitchAutomation.ObsProcessId) {
        $obsProc = Get-Process -Id $global:SwitchAutomation.ObsProcessId -ErrorAction SilentlyContinue
        if ($obsProc) {
            Write-SwitchLog "Closing OBS PID $($obsProc.Id)."
            $obsProc.CloseMainWindow() | Out-Null
            Start-Sleep -Seconds 5
            if (-not $obsProc.HasExited) {
                Write-SwitchLog "OBS did not close in time; forcing shutdown."
                Stop-Process -Id $obsProc.Id -Force -ErrorAction SilentlyContinue
            }
        }
    } else {
        Write-SwitchLog "Leaving OBS open because this Playnite session did not start it."
    }

    $global:SwitchAutomation = $null
} else {
    Write-SwitchLog "No SwitchAutomation session state was found during Exit."
}

Write-SwitchLog "Playnite Switch cleanup completed."
