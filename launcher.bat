@echo off
chcp 65001 >nul
title 2-Stroke Engine Simulation Launcher

:menu
cls
echo ==========================================
echo    2-Stroke Engine Simulation Launcherecho ==========================================
echo.
echo   [1] Run Python/PyGame Version
echo   [2] Run Godot Engine Version
echo   [3] Run Both (Physics Server + Godot)
echo   [4] Open Godot Project in Editor
echo.
echo   [Q] Quit
echo.
echo ==========================================
set /p choice="Select option: "

if "%choice%"=="1" goto python
if "%choice%"=="2" goto godot
if "%choice%"=="3" goto both
if "%choice%"=="4" goto editor
if /i "%choice%"=="q" exit /b 0
goto menu

:python
cls
echo Starting Python/PyGame version...
cd /d "%~dp0"
python main.py
if errorlevel 1 (
    echo.
    echo Error: Failed to start Python version.
    echo Make sure Python and PyGame are installed.
    pause
)
goto menu

:godot
cls
echo Starting Godot Engine version...
cd /d "%~dp0\godot_engine"
call launch.bat
goto menu

:both
cls
echo Starting both Physics Server and Godot Engine...
cd /d "%~dp0\godot_engine"
call launch.bat
goto menu

:editor
cls
cd /d "%~dp0\godot_engine"
set GODOT_PATH=Godot_v4.6.2-stable_win64.exe
if not exist "%GODOT_PATH%" (
    echo ERROR: Godot not found!
    echo Please download Godot 4.6.2 from https://godotengine.org/
    echo and place it in the godot_engine directory.
    pause
    goto menu
)
echo Opening Godot Editor...
start "Godot Editor" "%GODOT_PATH%" --editor --path "%~dp0\godot_engine"
goto menu
