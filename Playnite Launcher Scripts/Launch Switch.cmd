@echo off
setlocal
py -3 "%~dp0switch_launcher.py" %*
exit /b %ERRORLEVEL%
