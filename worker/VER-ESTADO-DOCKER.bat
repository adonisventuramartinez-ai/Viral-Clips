@echo off
setlocal
set "VAGRANT=C:\HashiCorp\Vagrant\bin"
set "PATH=%VAGRANT%;%PATH%"
cd /d C:\DockerVM\vagrant

echo ==== CONTENEDORES ====
"%VAGRANT%\vagrant.exe" ssh -c "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
echo.
echo ==== CPU / RAM ====
"%VAGRANT%\vagrant.exe" ssh -c "docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}'"
echo.
echo ==== ULTIMOS LOGS ====
"%VAGRANT%\vagrant.exe" ssh -c "docker logs --tail 25 clipforge-worker"
echo.
pause
