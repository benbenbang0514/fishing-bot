@echo off
pushd "%~dp0"

echo ============================================
echo   Auto-Fishing Bot - One-Click Launcher
echo ============================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [*] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [!] Failed to create .venv. Make sure Python 3.10+ is installed and in PATH.
        pause
        exit /b 1
    )
    echo [✓] Virtual environment created.
    echo.
)

echo [*] Installing/updating dependencies...
.venv\Scripts\pip.exe install -r requirements.txt --quiet
if errorlevel 1 (
    echo [!] Failed to install dependencies.
    pause
    exit /b 1
)
echo [✓] Dependencies ready.
echo.

echo [*] Checking administrator privileges...
powershell -NoProfile -Command "exit ([int]-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))" >nul 2>&1
if errorlevel 1 (
    echo [*] Requesting administrator privileges...
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_as_admin.ps1" %*
    popd
    exit /b 0
)
echo [✓] Running with administrator privileges.
echo.

echo [*] Launching Fishing Bot...
echo.
.venv\Scripts\python.exe main.py %*

echo.
echo Bot stopped.
pause
