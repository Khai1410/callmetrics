#!/bin/sh
cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
    echo "[Loi] Khong tim thay Docker. Vui long cai Docker Desktop truoc: https://www.docker.com/products/docker-desktop/"
    exit 1
fi

echo "Dang build va khoi dong CallMetrics, lan dau co the mat vai phut..."
docker compose up -d --build

echo ""
echo "Da khoi dong xong. Mo trinh duyet vao: http://localhost:${FRONTEND_PORT:-8081}"
