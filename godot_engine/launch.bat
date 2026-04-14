@echo off
chcp 65001 >nul
echo ==========================================
echo 2-Stroke Engine Simulation v3.0 Launcher
echo ==========================================
echo.

set GODOT_PATH=Godot_v4.6.2-stable_win64.exe
set PROJECT_PATH=%~dp0
set PROJECT_PATH=%PROJECT_PATH:~0,-1%

if not exist "%GODOT_PATH%" (
    echo ERROR: Godot not found!
    echo Please download Godot 4.6.2 from https://godotengine.org/
    echo and place it in this directory.
    echo.
    pause
    exit /b 1
)

echo [1/3] Starting Physics Server...
start "Physics Server" cmd /c "cd /d %PROJECT_PATH% && python scripts\physics_server.py"

echo [2/3] Waiting for physics server to initialize...
timeout /t 2 /nobreak >nul

echo [3/3] Starting Godot Engine...
start "Godot Engine" "%GODOT_PATH%" --path "%PROJECT_PATH%"

echo.
echo Both services started!
echo - Physics Server: TCP port 9999
echo - Godot Engine: Starting...
echo.
echo Press any key to stop all services...
pause >nul

echo.
echo Stopping services...
echo Killing physics server...
taskkill /F /FI "WINDOWTITLE eq Physics Server*" 2>nul
taskkill /F /IM python.exe /T 2>nul

echo Killing Godot Engine...
taskkill /F /FI "WINDOWTITLE eq Godot Engine*" 2>nul

echo Done!
timeout /t 2 /nobreak >nul
