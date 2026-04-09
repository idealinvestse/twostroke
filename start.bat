@echo off
echo Starting 2-stroke engine simulation...
cd /d "%~dp0"
python main.py
if errorlevel 1 (
    echo.
    echo Error: Failed to start simulation.
    echo Make sure Python and PyGame are installed.
    pause
)
