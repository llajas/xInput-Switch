<# Playnite emulator "General" executable target.
   This process gives Playnite a session to track. It waits for the OBS
   projector window to appear, then exits when that window closes. #>

$ErrorActionPreference = "Stop"

$projectorTitle = "Projector"
$startupTimeoutSeconds = 45
$missingWindowGraceSeconds = 15
$pollSeconds = 1
$baseDir = "C:\Nintendo Automation\xInput-Switch"
$logFile = Join-Path $baseDir "Playnite Launcher Scripts\playnite-switch-session.log"
$settingsFile = Join-Path $baseDir "config\switch_automation.settings.json"
$sessionExitSignalFile = Join-Path $baseDir "Playnite Launcher Scripts\switch-session-exit.signal"

if (-not ("Win32Window" -as [type])) {
    Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;

public static class Win32Window
{
    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    [DllImport("kernel32.dll")]
    public static extern IntPtr GetConsoleWindow();

    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

    [DllImport("user32.dll")]
    public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    public static extern int GetWindowTextLength(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool IsWindowVisible(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
}
"@
}

$consoleWindow = [Win32Window]::GetConsoleWindow()
if ($consoleWindow -ne [IntPtr]::Zero) {
    [Win32Window]::ShowWindow($consoleWindow, 0) | Out-Null
}

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
        $projectorTitle = [string](Get-Setting $settings "projectorTitle" $projectorTitle)
        $sessionExitSignalFile = [string](Get-Setting $settings "sessionExitSignalFile" $sessionExitSignalFile)
        Write-SwitchLog "Session host loaded settings from $settingsFile."
    }
    catch {
        Write-SwitchLog "Session host could not load settings from $settingsFile. Using defaults. Error: $($_.Exception.Message)"
    }
}

function Test-ProjectorWindow {
    $script:ProjectorWindowFound = $false
    $script:ProjectorWindowTitle = $null
    $script:ProjectorWindowHandle = [IntPtr]::Zero

    $callback = [Win32Window+EnumWindowsProc]{
        param([IntPtr]$hWnd, [IntPtr]$lParam)

        if (-not [Win32Window]::IsWindowVisible($hWnd)) {
            return $true
        }

        $length = [Win32Window]::GetWindowTextLength($hWnd)
        if ($length -le 0) {
            return $true
        }

        $builder = New-Object System.Text.StringBuilder ($length + 1)
        [Win32Window]::GetWindowText($hWnd, $builder, $builder.Capacity) | Out-Null
        $title = $builder.ToString()

        if ($title -like "*$projectorTitle*") {
            $script:ProjectorWindowFound = $true
            $script:ProjectorWindowTitle = $title
            $script:ProjectorWindowHandle = $hWnd
            return $false
        }

        return $true
    }

    [Win32Window]::EnumWindows($callback, [IntPtr]::Zero) | Out-Null
    return $script:ProjectorWindowFound
}

function Close-ProjectorWindow {
    if (Test-ProjectorWindow -and $script:ProjectorWindowHandle -ne [IntPtr]::Zero) {
        Write-SwitchLog "Closing projector window '$script:ProjectorWindowTitle' due to session exit signal."
        [Win32Window]::PostMessage($script:ProjectorWindowHandle, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero) | Out-Null
    }
}

Write-SwitchLog "Session host started; waiting for projector window."

$deadline = (Get-Date).AddSeconds($startupTimeoutSeconds)
while ((Get-Date) -lt $deadline) {
    if (Test-ProjectorWindow) {
        Write-SwitchLog "Projector window detected; session host is tracking '$script:ProjectorWindowTitle'."
        break
    }

    Start-Sleep -Seconds $pollSeconds
}

if (-not (Test-ProjectorWindow)) {
    Write-SwitchLog "Projector window was not detected before timeout."
    exit 1
}

$missingSince = $null
while ($true) {
    if (Test-Path -LiteralPath $sessionExitSignalFile) {
        Write-SwitchLog "Session exit signal detected."
        Remove-Item -LiteralPath $sessionExitSignalFile -Force -ErrorAction SilentlyContinue
        Close-ProjectorWindow
        break
    }

    if (Test-ProjectorWindow) {
        if ($null -ne $missingSince) {
            Write-SwitchLog "Projector window recovered; tracking '$script:ProjectorWindowTitle'."
            $missingSince = $null
        }
        Start-Sleep -Seconds $pollSeconds
        continue
    }

    if ($null -eq $missingSince) {
        $missingSince = Get-Date
        Write-SwitchLog "Projector window is not currently visible; waiting up to $missingWindowGraceSeconds seconds before exiting."
    }

    if (((Get-Date) - $missingSince).TotalSeconds -ge $missingWindowGraceSeconds) {
        break
    }

    Start-Sleep -Seconds $pollSeconds
}

Write-SwitchLog "Projector window closed; session host exiting."
exit 0
