<# Playnite "Pre" script.
   Starts OBS before Playnite launches the game action. #>

$ErrorActionPreference = "Stop"

$baseDir = "C:\Nintendo Automation\xInput-Switch"
$obsDir = "C:\Program Files\obs-studio\bin\64bit"
$obsExe = Join-Path $obsDir "obs64.exe"
$logFile = Join-Path $baseDir "Playnite Launcher Scripts\playnite-switch-session.log"
$settingsFile = Join-Path $baseDir "config\switch_automation.settings.json"

function Write-SwitchLog {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $logFile -Value $line
}

function Get-Setting {
    param(
        [object]$Settings,
        [string]$Name,
        [object]$Default
    )
    if ($null -ne $Settings -and $Settings.PSObject.Properties.Name -contains $Name -and $null -ne $Settings.$Name) {
        return $Settings.$Name
    }
    return $Default
}

$settings = $null
if (Test-Path -LiteralPath $settingsFile) {
    try {
        $settings = Get-Content -Path $settingsFile -Raw | ConvertFrom-Json
        Write-SwitchLog "Loaded settings from $settingsFile."
    }
    catch {
        Write-SwitchLog "Unable to load settings from $settingsFile. Using built-in defaults. Error: $($_.Exception.Message)"
    }
}
else {
    Write-SwitchLog "Settings file was not found at $settingsFile. Using built-in defaults."
}

$obsDir = [string](Get-Setting $settings "obsDir" $obsDir)
$obsExe = [string](Get-Setting $settings "obsExe" $obsExe)

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
