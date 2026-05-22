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
$settingsFile = Join-Path $global:SwitchAutomation.BaseDir "config\switch_automation.settings.json"
$logFile = $global:SwitchAutomation.LogFile
$bridgeLogFile = Join-Path $global:SwitchAutomation.BaseDir "Playnite Launcher Scripts\xinput2serial.log"
$bridgeProcessOutLogFile = Join-Path $global:SwitchAutomation.BaseDir "Playnite Launcher Scripts\xinput2serial-process.out.log"
$bridgeProcessErrLogFile = Join-Path $global:SwitchAutomation.BaseDir "Playnite Launcher Scripts\xinput2serial-process.err.log"
$bridgePidFile = Join-Path $global:SwitchAutomation.BaseDir "Playnite Launcher Scripts\xinput2serial.pid"

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

function ConvertTo-ProcessArgument {
    param([string]$Argument)
    '"' + ($Argument -replace '"', '\"') + '"'
}

function Join-ProcessArguments {
    param([string[]]$Arguments)
    ($Arguments | ForEach-Object { ConvertTo-ProcessArgument $_ }) -join " "
}

function Stop-ExistingBridgeProcesses {
    param([string]$ScriptPath)

    $normalized = $ScriptPath.ToLowerInvariant()
    $processes = @()
    try {
        $processes = Get-CimInstance Win32_Process | Where-Object {
            $_.ProcessId -ne $PID -and
            $_.Name -in @("python.exe", "pythonw.exe", "py.exe") -and
            $_.CommandLine -and
            $_.CommandLine.ToLowerInvariant().Contains($normalized)
        }
    }
    catch {
        Write-SwitchLog "Unable to inspect existing xinput2serial processes: $($_.Exception.Message)"
        return
    }

    foreach ($process in $processes) {
        Write-SwitchLog "Stopping existing xinput2serial process PID $($process.ProcessId) before starting Playnite bridge."
        Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

if (-not (Test-Path -LiteralPath $projectorScript)) {
    throw "OBS projector script was not found: $projectorScript"
}
if (-not (Test-Path -LiteralPath $xinputScript)) {
    throw "xinput2serial script was not found: $xinputScript"
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

$pythonExe = [string](Get-Setting $settings "pythonExe" $pythonExe)
$projectorTitle = [string](Get-Setting $settings "projectorTitle" $projectorTitle)
$mode = [string](Get-Setting $settings "playniteMode" "controller")
$controllerBackend = [string](Get-Setting $settings "controllerBackend" "auto")
$debugBridge = [bool](Get-Setting $settings "debugBridge" $false)
$serialPort = [string](Get-Setting $settings "serialPort" "COM3")
$controllerSlot = Get-Setting $settings "controllerSlot" 0
$bindToProjectorFocus = [bool](Get-Setting $settings "bindToProjectorFocus" $true)
$inactiveAction = [string](Get-Setting $settings "inactiveAction" "home")
$disconnectAction = [string](Get-Setting $settings "disconnectAction" "home")
$homeDuration = [double](Get-Setting $settings "homeDuration" 0.25)
$homeCooldown = [double](Get-Setting $settings "homeCooldown" 5.0)
$socketHost = [string](Get-Setting $settings "socketHost" "127.0.0.1")
$socketPort = [int](Get-Setting $settings "socketPort" 8765)
$socketStatusFile = [string](Get-Setting $settings "socketStatusFile" (Join-Path $global:SwitchAutomation.BaseDir "Playnite Launcher Scripts\xinput2serial-socket-status.json"))
$sessionExitSignalFile = [string](Get-Setting $settings "sessionExitSignalFile" (Join-Path $global:SwitchAutomation.BaseDir "Playnite Launcher Scripts\switch-session-exit.signal"))

if ($mode -notin @("controller", "socket", "keyboard")) {
    Write-SwitchLog "Unknown mode '$mode'. Falling back to controller mode."
    $mode = "controller"
}
if ($controllerBackend -notin @("auto", "xinput", "pygame")) {
    Write-SwitchLog "Unknown controller backend '$controllerBackend'. Falling back to auto."
    $controllerBackend = "auto"
}
if ($inactiveAction -notin @("neutral", "home", "none")) {
    Write-SwitchLog "Unknown inactive action '$inactiveAction'. Falling back to home."
    $inactiveAction = "home"
}
if ($disconnectAction -notin @("neutral", "home", "none")) {
    Write-SwitchLog "Unknown disconnect action '$disconnectAction'. Falling back to home."
    $disconnectAction = "home"
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

$backend = if ($mode -eq "socket") { "socket" } elseif ($mode -eq "keyboard") { $controllerBackend } else { $controllerBackend }
$xinputArgs = @($xinputScript, "--auto", "--backend", $backend, "--startup-debug", "--log-file", $bridgeLogFile)
if ($bindToProjectorFocus) {
    $xinputArgs += @("--window", $projectorTitle, "--inactive-action", $inactiveAction)
}
else {
    $xinputArgs += @("--inactive-action", "neutral")
}
$xinputArgs += @("--disconnect-action", $disconnectAction, "--home-duration", ([string]$homeDuration), "--home-cooldown", ([string]$homeCooldown))
$xinputArgs += @("--exit-chord-signal-file", $sessionExitSignalFile)
if ($mode -eq "keyboard") {
    $xinputArgs += "--keyboard"
}
if ($mode -eq "socket") {
    $xinputArgs += @("--socket-host", $socketHost, "--socket-port", ([string]$socketPort), "--socket-status-file", $socketStatusFile)
}
if ($debugBridge) {
    $xinputArgs += "--debug"
}
if ($serialPort) {
    $xinputArgs += @("--port", $serialPort)
}
if ($mode -ne "socket" -and $null -ne $controllerSlot -and [string]$controllerSlot -ne "") {
    $xinputArgs += @("--controller", [string]$controllerSlot)
}

Write-SwitchLog "Starting xinput2serial."
Stop-ExistingBridgeProcesses -ScriptPath $xinputScript
Remove-Item -LiteralPath $sessionExitSignalFile -Force -ErrorAction SilentlyContinue
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
