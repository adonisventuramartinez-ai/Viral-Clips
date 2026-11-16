# Enciende el worker de ClipForge EN SEGUNDO PLANO y lo deja siempre activo (se levanta solo). Se ejecuta desde INICIAR-SIEMPRE.bat
Set-Location $PSScriptRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker no esta instalado o no esta abierto. Instala Docker Desktop (docker.com/products/docker-desktop), abrelo y vuelve a ejecutar." -ForegroundColor Red
    exit 1
}
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker Desktop esta instalado pero no esta corriendo. Abrelo, espera a que diga 'running' y vuelve a ejecutar." -ForegroundColor Red
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

$env:YTDLP_BUST = Get-Date -Format "yyyyMMddHH"
Write-Host "Construyendo y encendiendo el worker (la primera vez tarda unos minutos)..." -ForegroundColor Cyan
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { Write-Host "Fallo. Mira el mensaje de arriba." -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "Worker encendido en segundo plano y siempre activo." -ForegroundColor Green
Write-Host "  - Puedes cerrar esta ventana. Si se cae o reinicias la PC, vuelve solo."
Write-Host "  - IMPORTANTE: en Docker Desktop > Settings > General marca 'Start Docker Desktop when you sign in'."
Write-Host "  - Ver que hace: VER-LOGS.bat   |   Apagarlo: DETENER-WORKER.bat"
Start-Sleep -Seconds 8
docker compose ps
