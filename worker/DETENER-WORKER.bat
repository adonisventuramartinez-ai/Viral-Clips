@echo off
cd /d "%~dp0"
docker compose down
echo.
echo Worker apagado. Para volver a encenderlo: INICIAR-SIEMPRE.bat
pause
