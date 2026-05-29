@echo off
setlocal
cd /d "%~dp0"

python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 exit /b %errorlevel%

python -m PyInstaller --clean --noconfirm Fuzzyficator.spec
if errorlevel 1 exit /b %errorlevel%

echo.
echo Built dist\Fuzzyficator\Fuzzyficator.exe
