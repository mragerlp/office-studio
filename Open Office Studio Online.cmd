@echo off
setlocal
call "%~dp0Start Office Studio.cmd" --online
exit /b %errorlevel%
