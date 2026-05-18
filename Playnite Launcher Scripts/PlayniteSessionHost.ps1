<# Playnite emulator "General" executable target.
   This process gives Playnite a session to track. It waits for the OBS
   projector window to appear, then exits when that window closes. #>

$ErrorActionPreference = "Stop"

$projectorTitle = "Windowed Projector (Source) - Scene"
$startupTimeoutSeconds = 45
$pollSeconds = 1
$baseDir = "C:\Nintendo Automation\xInput-Switch"
$logFile = Join-Path $baseDir "Playnite Launcher Scripts\playnite-switch-session.log"

function Write-SwitchLog {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $logFile -Value $line
}

function Test-ProjectorWindow {
    Get-Process -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowTitle -like "*$projectorTitle*" } |
        Select-Object -First 1
}

Write-SwitchLog "Session host started; waiting for projector window."

$deadline = (Get-Date).AddSeconds($startupTimeoutSeconds)
while ((Get-Date) -lt $deadline) {
    if (Test-ProjectorWindow) {
        Write-SwitchLog "Projector window detected; session host is tracking it."
        break
    }

    Start-Sleep -Seconds $pollSeconds
}

if (-not (Test-ProjectorWindow)) {
    Write-SwitchLog "Projector window was not detected before timeout."
    exit 1
}

while (Test-ProjectorWindow) {
    Start-Sleep -Seconds $pollSeconds
}

Write-SwitchLog "Projector window closed; session host exiting."
exit 0
