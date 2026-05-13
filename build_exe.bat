@echo off
REM Build a single-file Windows EXE for Perch.
REM Requires:  pip install -r requirements.txt -r requirements-dev.txt

setlocal
pushd "%~dp0"

where pyinstaller >nul 2>nul
if errorlevel 1 (
    echo PyInstaller not found. Install with: pip install -r requirements-dev.txt
    exit /b 1
)

pyinstaller --noconfirm --onefile --windowed ^
    --name "Perch" ^
    --icon "assets/perch.ico" ^
    --add-data "assets/perch.png;assets" ^
    --add-data "assets/perch.ico;assets" ^
    --collect-all customtkinter ^
    run.py
if errorlevel 1 (
    echo Build failed.
    exit /b 1
)

echo.
echo Build complete: dist\Perch.exe
popd
endlocal
