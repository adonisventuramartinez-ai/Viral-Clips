# Enciende el worker de ClipForge EN SEGUNDO PLANO y lo deja siempre activo (se levanta solo). Se ejecuta desde INICIAR-SIEMPRE.bat
Set-Location $PSScriptRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker no esta instalado o no está en el PATH. Instala Docker Desktop o Docker Toolbox y vuelve a ejecutar." -ForegroundColor Red
    exit 1
}
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker esta instalado pero el daemon no responde. Abre Docker Desktop o corre 'docker-machine env default' (Toolbox) y vuelve a ejecutar." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path ".env")) {
    Write-Host "Falta worker\.env. Ejecuta primero INICIAR-WORKER.bat una vez (te pide los 3 datos) y luego usa este." -ForegroundColor Red
    exit 1
}

# Si tenias el worker abierto con INICIAR-WORKER.bat, hay que cerrarlo: dos workers a la vez se pisarian los trabajos
$old = docker ps --filter "ancestor=clipforge-worker" --filter "status=running" --format "{{.Names}}" | Where-Object { $_ -ne "clipforge-worker" }
if ($old) {
    Write-Host "Hay otro worker corriendo ($old). Cierra la ventana de INICIAR-WORKER.bat y vuelve a ejecutar." -ForegroundColor Yellow
    exit 1
}

# Docker Desktop trae 'docker compose' (v2); Docker Toolbox solo trae el binario 'docker-compose' (v1).
$composeSub = if ((docker compose version *> $null) -and ($LASTEXITCODE -eq 0)) { @('compose') } else { @() }
$env:YTDLP_BUST = Get-Date -Format "yyyyMMddHH"
Write-Host "Construyendo y encendiendo el worker (la primera vez tarda unos minutos)..." -ForegroundColor Cyan
if ($composeSub.Count) { & docker @composeSub up -d --build } else { & docker-compose up -d --build }
if ($LASTEXITCODE -ne 0) { Write-Host "Fallo. Mira el mensaje de arriba." -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "Worker encendido en segundo plano y siempre activo." -ForegroundColor Green
Write-Host "  - Puedes cerrar esta ventana. Si se cae o reinicias la PC, vuelve solo."
Write-Host "  - IMPORTANTE: deja el daemon de Docker (Desktop o VM de Toolbox) corriendo al iniciar Windows."
Write-Host "  - Ver que hace: VER-LOGS.bat   |   Apagarlo: DETENER-WORKER.bat"
Start-Sleep -Seconds 8
if ($composeSub.Count) { & docker @composeSub ps } else { & docker-compose ps }
