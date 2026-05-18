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

$pythonExe = "python.exe"
$projectorTitle = "Windowed Projector (Source) - Scene"
$projectorScript = Join-Path $global:SwitchAutomation.BaseDir "Playnite Launcher Scripts\start_obs_fullscreen.py"
$xinputScript = Join-Path $global:SwitchAutomation.BaseDir "xInput2Serial\xinput2serial.py"
$logFile = $global:SwitchAutomation.LogFile
$bridgeLogFile = Join-Path $global:SwitchAutomation.BaseDir "Playnite Launcher Scripts\xinput2serial.log"

# Optional xinput2serial settings.
$useKeyboardMouse = $false
$debugBridge = $false
$serialPort = $null
$controllerSlot = $null

function Write-SwitchLog {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $logFile -Value $line
}

function ConvertTo-ProcessArgument {
    param([string]$Argument)
    '"' + ($Argument -replace '"', '\"') + '"'
}

if (-not (Test-Path -LiteralPath $projectorScript)) {
    throw "OBS projector script was not found: $projectorScript"
}
if (-not (Test-Path -LiteralPath $xinputScript)) {
    throw "xinput2serial script was not found: $xinputScript"
}

Write-SwitchLog "Opening OBS projector."
$projectorProc = Start-Process -FilePath $pythonExe -ArgumentList (ConvertTo-ProcessArgument $projectorScript) -PassThru -WindowStyle Hidden
$global:SwitchAutomation.ProjectorProcessId = $projectorProc.Id
$projectorProc.WaitForExit(15000) | Out-Null
if (-not $projectorProc.HasExited) {
    Write-SwitchLog "Projector script is still running after 15 seconds; continuing."
} elseif ($projectorProc.ExitCode -ne 0) {
    throw "OBS projector script failed with exit code $($projectorProc.ExitCode)."
}

$xinputArgs = @($xinputScript, "--auto", "--window", $projectorTitle, "--startup-debug", "--log-file", $bridgeLogFile)
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
$xinputProc = Start-Process -FilePath $pythonExe -ArgumentList (($xinputArgs | ForEach-Object { ConvertTo-ProcessArgument $_ }) -join " ") -PassThru -WindowStyle Hidden
$global:SwitchAutomation.XInputProcessId = $xinputProc.Id
Write-SwitchLog "xinput2serial started as PID $($xinputProc.Id)."

Start-Sleep -Seconds 2
if ($xinputProc.HasExited) {
    $tail = Get-Content -Path $bridgeLogFile -ErrorAction SilentlyContinue | Select-Object -Last 20
    Write-SwitchLog "xinput2serial exited early with code $($xinputProc.ExitCode). Recent bridge log:"
    foreach ($line in $tail) {
        Write-SwitchLog "  $line"
    }
    throw "xinput2serial exited early. See $bridgeLogFile"
}
