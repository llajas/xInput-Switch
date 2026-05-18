<# Playnite "Post" script.
   Opens the OBS projector and starts xinput2serial after the game action starts. #>

$ErrorActionPreference = "Stop"

if (-not $global:SwitchAutomation) {
    $baseDir = "C:\Nintendo Automation\xInput-Switch"
    $global:SwitchAutomation = @{
        BaseDir = $baseDir
        ObsStartedByPlaynite = $false
        XInputProcessId = $null
        ProjectorProcessId = $null
        LogFile = Join-Path $baseDir "Playnite Launcher Scripts\playnite-switch-session.log"
    }
}

$pythonExe = "C:\Python312\python.exe"
$projectorTitle = "Projector"
$projectorScript = Join-Path $global:SwitchAutomation.BaseDir "Playnite Launcher Scripts\start_obs_fullscreen.py"
$xinputScript = Join-Path $global:SwitchAutomation.BaseDir "xInput2Serial\xinput2serial.py"
$logFile = $global:SwitchAutomation.LogFile
$bridgeLogFile = Join-Path $global:SwitchAutomation.BaseDir "Playnite Launcher Scripts\xinput2serial.log"
$bridgeProcessOutLogFile = Join-Path $global:SwitchAutomation.BaseDir "Playnite Launcher Scripts\xinput2serial-process.out.log"
$bridgeProcessErrLogFile = Join-Path $global:SwitchAutomation.BaseDir "Playnite Launcher Scripts\xinput2serial-process.err.log"
$bridgePidFile = Join-Path $global:SwitchAutomation.BaseDir "Playnite Launcher Scripts\xinput2serial.pid"

# Optional xinput2serial settings.
$useKeyboardMouse = $false
$debugBridge = $false
$serialPort = "COM3"
$controllerSlot = 0
$bindToProjectorFocus = $true

function Write-SwitchLog {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $logFile -Value $line
}

function ConvertTo-ProcessArgument {
    param([string]$Argument)
    '"' + ($Argument -replace '"', '\"') + '"'
}

function Join-ProcessArguments {
    param([string[]]$Arguments)
    ($Arguments | ForEach-Object { ConvertTo-ProcessArgument $_ }) -join " "
}

if (-not (Test-Path -LiteralPath $projectorScript)) {
    throw "OBS projector script was not found: $projectorScript"
}
if (-not (Test-Path -LiteralPath $xinputScript)) {
    throw "xinput2serial script was not found: $xinputScript"
}

Write-SwitchLog "Opening OBS projector."
$projectorCommand = "$(ConvertTo-ProcessArgument $pythonExe) $(ConvertTo-ProcessArgument $projectorScript)"
Write-SwitchLog "Projector command: $projectorCommand"
$projectorProc = Start-Process -FilePath $pythonExe -ArgumentList (ConvertTo-ProcessArgument $projectorScript) -PassThru -WindowStyle Hidden
$global:SwitchAutomation.ProjectorProcessId = $projectorProc.Id
$projectorProc.WaitForExit(15000) | Out-Null
if (-not $projectorProc.HasExited) {
    Write-SwitchLog "Projector script is still running after 15 seconds; continuing."
} elseif ($projectorProc.ExitCode -ne 0) {
    throw "OBS projector script failed with exit code $($projectorProc.ExitCode)."
}

$xinputArgs = @($xinputScript, "--auto", "--startup-debug", "--log-file", $bridgeLogFile)
if ($bindToProjectorFocus) {
    $xinputArgs += @("--window", $projectorTitle, "--inactive-action", "home")
}
else {
    $xinputArgs += @("--inactive-action", "neutral")
}
$xinputArgs += @("--disconnect-action", "home", "--home-duration", "0.25", "--home-cooldown", "5")
if ($useKeyboardMouse) {
    $xinputArgs += "--keyboard"
}
if ($debugBridge) {
    $xinputArgs += "--debug"
}
if ($serialPort) {
    $xinputArgs += @("--port", $serialPort)
}
if ($null -ne $controllerSlot) {
    $xinputArgs += @("--controller", [string]$controllerSlot)
}

Write-SwitchLog "Starting xinput2serial."
$xinputCommand = "$(ConvertTo-ProcessArgument $pythonExe) $(Join-ProcessArguments $xinputArgs)"
Write-SwitchLog "xinput2serial command: $xinputCommand"
$xinputProc = Start-Process -FilePath $pythonExe -ArgumentList (Join-ProcessArguments $xinputArgs) -PassThru -WindowStyle Hidden -RedirectStandardOutput $bridgeProcessOutLogFile -RedirectStandardError $bridgeProcessErrLogFile
$global:SwitchAutomation.XInputProcessId = $xinputProc.Id
Set-Content -Path $bridgePidFile -Value $xinputProc.Id
Write-SwitchLog "xinput2serial started as PID $($xinputProc.Id)."

Start-Sleep -Seconds 2
if ($xinputProc.HasExited) {
    $tail = @()
    $tail += Get-Content -Path $bridgeLogFile -ErrorAction SilentlyContinue | Select-Object -Last 10
    $tail += Get-Content -Path $bridgeProcessOutLogFile -ErrorAction SilentlyContinue | Select-Object -Last 10
    $tail += Get-Content -Path $bridgeProcessErrLogFile -ErrorAction SilentlyContinue | Select-Object -Last 10
    Write-SwitchLog "xinput2serial exited early with code $($xinputProc.ExitCode). Recent bridge log:"
    foreach ($line in $tail) {
        Write-SwitchLog "  $line"
    }
    throw "xinput2serial exited early. See $bridgeLogFile"
}
