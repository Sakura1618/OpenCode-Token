@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT_DIR=%%~fI"

pushd "%ROOT_DIR%"

if not exist "build" mkdir "build"

if exist "build\opencode_token_gui.exe" del /f /q "build\opencode_token_gui.exe"
if exist "build\opencode_token_gui" rmdir /s /q "build\opencode_token_gui"
if exist "build\pyinstaller" rmdir /s /q "build\pyinstaller"

python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [build] Installing PyInstaller...
    python -m pip install .[build]
    if errorlevel 1 exit /b 1
)

echo [build] Building single-file executable...
python -m PyInstaller --noconfirm --clean --distpath "%ROOT_DIR%\build" --workpath "%ROOT_DIR%\build\pyinstaller" "%ROOT_DIR%\opencode_token_gui.spec"
if errorlevel 1 exit /b 1

echo [build] Done: build\opencode_token_gui.exe
popd
exit /b 0
