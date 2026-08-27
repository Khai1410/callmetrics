@echo off
cd /d "%~dp0"

where docker >nul 2>nul
if errorlevel 1 (
    echo [Loi] Khong tim thay Docker. Vui long cai Docker Desktop truoc: https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)

echo Dang build va khoi dong CallMetrics, lan dau co the mat vai phut...
docker compose up -d --build
if errorlevel 1 (
    echo.
    echo [Loi] Khoi dong that bai, xem log loi phia tren.
    pause
    exit /b 1
)

echo.
echo Da khoi dong xong. Mo trinh duyet vao: http://localhost:8081
echo (Neu 8081 bi trung port may khac, sua file .env: FRONTEND_PORT=... roi chay lai file nay)
pause
