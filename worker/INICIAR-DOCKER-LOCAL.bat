@echo off
setlocal
set "VAGRANT=C:\HashiCorp\Vagrant\bin"
set "PATH=%VAGRANT%;%PATH%"
cd /d C:\DockerVM\vagrant

echo.
echo ==== Verificando VM Ubuntu con Docker (Vagrant) ====
"%VAGRANT%\vagrant.exe" ssh -c "exit 0" >nul 2>&1
if errorlevel 1 (
  echo ==== Levantando VM ====
  "%VAGRANT%\vagrant.exe" up
  if errorlevel 1 goto :error
) else (
  echo La VM ya esta encendida; se omite 'vagrant up'.
)

echo.
echo ==== Construyendo y encendiendo el worker dentro de la VM ====
"%VAGRANT%\vagrant.exe" ssh -c "cd /vagrant && docker-compose up -d --build --force-recreate"
if errorlevel 1 goto :error

echo.
echo ==== Logs del worker (Ctrl+C para salir) ====
"%VAGRANT%\vagrant.exe" ssh -c "docker logs -f --tail 100 clipforge-worker"
exit /b 0

:error
echo.
echo Fallo. Revisa el mensaje de arriba.
pause
exit /b 1
