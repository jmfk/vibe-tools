@echo off
REM Vibe-Tools Installation Script for Windows

echo --- Installing Vibe-Tools ---

REM Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: python is not installed or not in PATH.
    exit /b 1
)

REM Determine if we should use editable mode (-e)
set "INSTALL_FLAGS="
if exist implementation\config.json (
    for /f "tokens=*" %%a in ('python -c "import json, pathlib; p = pathlib.Path('implementation/config.json'); print('true' if json.loads(p.read_text()).get('setup', {}).get('standalone', True) else 'false')" 2^>nul') do set "STANDALONE=%%a"
) else (
    set "STANDALONE=true"
)

if "%STANDALONE%"=="false" (
    set "INSTALL_FLAGS=-e"
    echo Using editable mode based on config (standalone: false)
) else (
    echo Using standalone installation mode (default)
)

REM Install the package
echo Installing package...
pip install %INSTALL_FLAGS% .

echo.
echo --- Installation Complete ---
echo You can now use the 'vibe' and 'vibe-setup' commands.
echo Try running: vibe --help or vibe-setup --help



