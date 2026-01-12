@echo off
REM Vibe-Tools Installation Script for Windows

set VERSION=0.1.0

echo --- Installing Vibe-Tools ---

REM Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: python is not installed or not in PATH.
    exit /b 1
)

REM Install the package in editable mode
echo Installing package...
pip install -e .

echo.
echo --- Installation Complete ---
echo You can now use the 'vibe' and 'vibe-setup' commands.
echo Try running: vibe --help or vibe-setup --help



