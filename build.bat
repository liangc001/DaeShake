@echo off
setlocal
cd /d "%~dp0"

py -3.12 -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing the build dependency...
    py -3.12 -m pip install --user -r requirements-build.txt
    if errorlevel 1 (
        echo Failed to install PyInstaller.
        exit /b 1
    )
)

py -3.12 -m PyInstaller --noconfirm --clean --onefile --windowed --name DaeShake --icon app_icon.ico --add-data "app_icon.ico;." --add-data "app_icon.png;." --add-data "ui_icons;ui_icons" screen_shaker.py
if errorlevel 1 (
    echo Build failed.
    exit /b 1
)

echo.
echo Built: %~dp0dist\DaeShake.exe
