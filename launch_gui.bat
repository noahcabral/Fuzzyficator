@echo off
setlocal
cd /d "%~dp0"
where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "%~dp0Fuzzyficator_gui.pyw"
) else (
    python "%~dp0Fuzzyficator_gui.py"
)
