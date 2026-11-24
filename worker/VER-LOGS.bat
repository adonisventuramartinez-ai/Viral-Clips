@echo off
cd /d "%~dp0"
docker compose ps
echo.
echo --- ultimas lineas (Ctrl+C para salir) ---
docker compose logs -f --tail 60 worker
