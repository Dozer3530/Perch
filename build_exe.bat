@echo off
REM Build a single-file Windows EXE for Image Sorter.
REM Requires:  pip install -r requirements.txt -r requirements-dev.txt

setlocal
pushd "%~dp0"

where pyinstaller >nul 2>nul
if errorlevel 1 (
    echo PyInstaller not found. Install with: pip install -r requirements-dev.txt
    exit /b 1
)

pyinstaller --noconfirm --onefile --windowed ^
    --name "ImageSorter" ^
    --collect-all customtkinter ^
    run.py
if errorlevel 1 (
    echo Build failed.
    exit /b 1
)

echo.
echo Build complete: dist\ImageSorter.exe
popd
endlocal
