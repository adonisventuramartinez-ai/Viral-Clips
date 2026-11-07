# Prepara y arranca el worker de ClipForge. Se ejecuta desde INICIAR-WORKER.bat
Set-Location $PSScriptRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host ""
    Write-Host "Docker no esta instalado o no esta abierto." -ForegroundColor Red
    Write-Host "Instala Docker Desktop (docker.com/products/docker-desktop), abrelo, espera a que diga 'running' y vuelve a ejecutar este archivo."
    exit 1
}

if (-not (Test-Path ".env")) {
    Write-Host "Primera vez: pega tus 3 datos (clic derecho para pegar) y presiona Enter en cada uno." -ForegroundColor Cyan
    $url = (Read-Host "1/3 SUPABASE_URL (https://xxxx.supabase.co)").Trim()
    $key = (Read-Host "2/3 SUPABASE_SERVICE_ROLE_KEY").Trim()
    $groq = (Read-Host "3/3 GROQ_API_KEY (gsk_...)").Trim()
    if (-not $url -or -not $key -or -not $groq) {
        Write-Host "Falto algun dato. Vuelve a ejecutar." -ForegroundColor Red
        exit 1
    }
    $lines = "SUPABASE_URL=$url", "SUPABASE_SERVICE_ROLE_KEY=$key", "GROQ_API_KEY=$groq", "LANGUAGE=es"
    # Se escribe con saltos de linea tipo Linux (LF) para que Docker lea bien los valores
    [System.IO.File]::WriteAllText((Join-Path $PSScriptRoot ".env"), ($lines -join "`n") + "`n")
    Write-Host "Listo: guarde tus datos en worker\.env (no se sube a GitHub)." -ForegroundColor Green
}

Write-Host "Construyendo el worker (la primera vez tarda unos minutos)..." -ForegroundColor Cyan
docker build -t clipforge-worker .
if ($LASTEXITCODE -ne 0) { Write-Host "Fallo la construccion de Docker." -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "Worker encendido. Dejalo abierto mientras procesas videos. Cierra esta ventana para apagarlo." -ForegroundColor Green
docker run --rm --env-file .env clipforge-worker
