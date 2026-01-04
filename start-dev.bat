@echo off
echo ========================================
echo   Agents SDK - Development Server
echo ========================================
echo.

cd /d D:\agents-sdk

echo [1/4] Stopping existing containers...
docker-compose down 2>nul

echo.
echo [2/4] Starting containers...
docker-compose up -d

echo.
echo [3/4] Waiting for tunnel to initialize...
timeout /t 8 /nobreak >NUL 2>&1

echo.
echo [4/4] Updating Firebase with new URL...
python scripts\update_tunnel_url.py

echo.
echo ========================================
echo   Server is ready!
echo   Health: [URL]/health
echo   Task:   [URL]/task
echo ========================================
pause
