@echo off
rem Arranca la VM y el worker SIN abrir ventanas de logs. Pon este archivo en el Inicio de Windows:
rem   Win+R -> shell:startup -> copiar este .bat ahi
setlocal
set "VAGRANT=C:\HashiCorp\Vagrant\bin"
set "PATH=%VAGRANT%;%PATH%"
set "LOG=%~dp0logs\inicio-docker-local.log"
cd /d C:\DockerVM\vagrant

if not exist "%VAGRANT%\vagrant.exe" (
  echo [%date% %time%] Falta Vagrant en %VAGRANT% >> "%LOG%"
  exit /b 1
)

"%VAGRANT%\vagrant.exe" up >> "%LOG%" 2>&1
if errorlevel 1 exit /b 1
"%VAGRANT%\vagrant.exe" ssh -c "cd /vagrant && docker-compose up -d --build" >> "%LOG%" 2>&1
exit /b %ERRORLEVEL%
