@echo off
setlocal
cd /d "%~dp0"
set "PYTHONDONTWRITEBYTECODE=1"
set "PATH=%SystemRoot%\System32;%PATH%"
if exist "%~dp0office-studio-runner.exe" goto use_runner
set "office_py=py"
if exist "%SystemRoot%\py.exe" set "office_py=%SystemRoot%\py.exe"
"%office_py%" -3 -B -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 goto use_py
set "office_python="
rem Skip Windows Store aliases; this launcher never invokes an installer.
for /f "delims=" %%P in ('where.exe python3 2^>nul ^| findstr.exe /v /i /l /c:"WindowsApps"') do call :check_python "%%P"
if defined office_python goto use_python
for /f "delims=" %%P in ('where.exe python 2^>nul ^| findstr.exe /v /i /l /c:"WindowsApps"') do call :check_python "%%P"
if defined office_python goto use_python
echo Python 3.10 or newer is required. Install Python 3, then open this launcher again.
pause
exit /b 1
:use_runner
"%~dp0office-studio-runner.exe" %*
goto finished
:use_py
"%office_py%" -3 -B "%~dp0launch.py" %*
goto finished
:use_python
"%office_python%" -B "%~dp0launch.py" %*
goto finished
:check_python
if defined office_python exit /b 0
"%~1" -B -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 set "office_python=%~1"
exit /b 0
:finished
set "office_status=%errorlevel%"
if not "%office_status%"=="0" pause
exit /b %office_status%
