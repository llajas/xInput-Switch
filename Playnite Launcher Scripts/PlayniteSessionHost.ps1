<# Playnite emulator "General" executable target.
   This process gives Playnite a session to track. It waits for the OBS
   projector window to appear, then exits when that window closes. #>

$ErrorActionPreference = "Stop"

$projectorTitle = "Projector"
$startupTimeoutSeconds = 45
$pollSeconds = 1
$baseDir = "C:\Nintendo Automation\xInput-Switch"
$logFile = Join-Path $baseDir "Playnite Launcher Scripts\playnite-switch-session.log"

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

function Test-ProjectorWindow {
    $script:ProjectorWindowFound = $false
    $script:ProjectorWindowTitle = $null

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
            return $false
        }

        return $true
    }

    [Win32Window]::EnumWindows($callback, [IntPtr]::Zero) | Out-Null
    return $script:ProjectorWindowFound
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

while (Test-ProjectorWindow) {
    Start-Sleep -Seconds $pollSeconds
}

Write-SwitchLog "Projector window closed; session host exiting."
exit 0
