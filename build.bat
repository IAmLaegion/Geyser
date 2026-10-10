@echo off
setlocal
cd /d "%~dp0"

if not exist venv (
    python -m venv venv || goto :fail
)
venv\Scripts\python -m pip install -q -r requirements-build.txt || goto :fail
venv\Scripts\python tools\prepare_build.py || goto :fail

venv\Scripts\pyinstaller --noconfirm --clean --windowed --onefile ^
    --name Geyser ^
    --icon build\geyser.ico ^
    --collect-submodules comtypes.gen ^
    --exclude-module tkinter ^
    run.py || goto :fail

echo.
echo Built dist\Geyser.exe
exit /b 0

:fail
echo.
echo Build failed.
exit /b 1
