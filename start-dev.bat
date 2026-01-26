@echo off
echo ========================================
echo   Agents SDK - Development Server
echo ========================================
echo.

cd /d D:\agents-sdk

echo [1/2] Stopping existing containers...
docker-compose down 2>nul

echo.
echo [2/2] Starting containers...
docker-compose up -d

echo.
echo ========================================
echo   Server is ready!
echo   Health: http://localhost:8000/health
echo   Task:   http://localhost:8000/task
echo ========================================
pause
