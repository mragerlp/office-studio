@echo off
setlocal
call "%~dp0Start Office Studio.cmd" --configure %*
exit /b %errorlevel%
