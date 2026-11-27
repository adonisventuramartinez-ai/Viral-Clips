@echo off
setlocal
set "VAGRANT=C:\HashiCorp\Vagrant\bin"
set "PATH=%VAGRANT%;%PATH%"
cd /d C:\DockerVM\vagrant
"%VAGRANT%\vagrant.exe" ssh -c "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
echo.
echo --- logs del worker (Ctrl+C para salir) ---
"%VAGRANT%\vagrant.exe" ssh -c "docker logs -f --tail 100 clipforge-worker"
