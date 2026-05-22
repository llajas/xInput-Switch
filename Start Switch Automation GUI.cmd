@echo off
setlocal
set "ROOT=%~dp0"
set "PYTHON=C:\Python312\python.exe"
if exist "%PYTHON%" (
  "%PYTHON%" "%ROOT%gui\SwitchAutomationGui.py"
) else (
  py -3 "%ROOT%gui\SwitchAutomationGui.py"
)
