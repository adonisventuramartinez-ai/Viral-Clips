@echo off
setlocal
set "VAGRANT=C:\HashiCorp\Vagrant\bin"
set "PATH=%VAGRANT%;%PATH%"
cd /d C:\DockerVM\vagrant

echo.
echo ==== Reiniciando el worker dentro de la VM (sin vagrant up) ====
"%VAGRANT%\vagrant.exe" ssh -c "cd /vagrant && docker-compose up -d --build --force-recreate"
if errorlevel 1 goto :error

echo.
echo ==== Logs del worker (Ctrl+C para salir) ====
"%VAGRANT%\vagrant.exe" ssh -c "docker logs -f --tail 100 clipforge-worker"
exit /b 0

:error
echo.
echo Fallo. Revisa el mensaje de arriba.
echo Si la VM esta apagada, abre C:\DockerVM\vagrant y corre: vagrant up
pause
exit /b 1
