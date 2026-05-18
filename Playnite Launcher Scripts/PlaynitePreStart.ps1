<# Playnite "Pre" script.
   Starts OBS before Playnite launches the game action. #>

$ErrorActionPreference = "Stop"

$baseDir = "C:\Nintendo Automation\xInput-Switch"
$obsDir = "C:\Program Files\obs-studio\bin\64bit"
$obsExe = Join-Path $obsDir "obs64.exe"
$logFile = Join-Path $baseDir "Playnite Launcher Scripts\playnite-switch-session.log"

function Write-SwitchLog {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $logFile -Value $line
}

$global:SwitchAutomation = @{
    BaseDir = $baseDir
    ObsDir = $obsDir
    ObsExe = $obsExe
    ObsWasRunning = $false
    ObsStartedByPlaynite = $false
    ObsProcessId = $null
    XInputProcessId = $null
    ProjectorProcessId = $null
    LogFile = $logFile
}

if (-not (Test-Path -LiteralPath $obsExe)) {
    throw "OBS executable was not found: $obsExe"
}

$obsProcess = Get-Process -Name "obs64" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($obsProcess) {
    $global:SwitchAutomation.ObsWasRunning = $true
    $global:SwitchAutomation.ObsProcessId = $obsProcess.Id
    Write-SwitchLog "OBS is already running as PID $($obsProcess.Id)."
    return
}

Write-SwitchLog "Starting OBS."
$startedObs = Start-Process -FilePath $obsExe -WorkingDirectory $obsDir -ArgumentList "--disable-shutdown-check" -PassThru
$global:SwitchAutomation.ObsStartedByPlaynite = $true
$global:SwitchAutomation.ObsProcessId = $startedObs.Id

Start-Sleep -Seconds 3
Write-SwitchLog "OBS started as PID $($startedObs.Id)."
