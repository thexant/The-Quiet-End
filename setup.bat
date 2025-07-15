@echo off
title Discord RPG Bot Setup
color 0A

echo ====================================
echo    DISCORD RPG BOT SETUP WIZARD
echo ====================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH!
    echo.
    echo Please install Python 3.8+ from https://python.org
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

REM Check if setup.py exists
if not exist "setup.py" (
    echo ERROR: setup.py not found!
    echo.
    echo Please ensure this batch file is in the same directory as setup.py
    echo.
    pause
    exit /b 1
)

REM Check if config.py exists (warn if not)
if not exist "config.py" (
    echo WARNING: config.py not found!
    echo The setup script will not be able to update bot configuration.
    echo.
    echo Press any key to continue anyway, or close this window to cancel...
    pause >nul
    echo.
)

REM Check if database.py exists (warn if not)
if not exist "database.py" (
    echo WARNING: database.py not found!
    echo The setup script will not be able to update database configuration.
    echo.
    echo Press any key to continue anyway, or close this window to cancel...
    pause >nul
    echo.
)

REM Run the setup script
echo Starting setup wizard...
echo.

python setup.py

REM Check if setup completed successfully
if %errorlevel% equ 0 (
    echo.
    echo Setup completed!
) else (
    echo.
    echo Setup encountered an error!
)

echo.
pause