# Pide al worker que pare TODOS los directos que estan grabando.
# Lee SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY de worker/.env. No muestra llaves.
param([string]$EnvFile = (Join-Path $PSScriptRoot '.env'))

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $EnvFile)) { throw 'No existe worker/.env' }

$v = @{}
foreach ($line in Get-Content -LiteralPath $EnvFile) {
  if ($line -match '^\s*([A-Z0-9_]+)\s*=\s*(.*)$') { $v[$Matches[1]] = $Matches[2].Trim() }
}
$url = $v['SUPABASE_URL']; if (-not $url) { $url = $v['NEXT_PUBLIC_SUPABASE_URL'] }
$key = $v['SUPABASE_SERVICE_ROLE_KEY']; if (-not $key) { $key = $v['SUPABASE_SECRET_KEY'] }
if (-not $url -or -not $key) { throw 'Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en worker/.env' }

$base = $url.TrimEnd('/')
$headers = @{
  'apikey' = $key
  'Authorization' = "Bearer $key"
  'Content-Type' = 'application/json'
  'Prefer' = 'return=minimal'
  'x-client-info' = 'parar-en-vivo'
  'User-Agent' = 'parar-en-vivo/1.0'
}

$estados = [uri]::EscapeDataString('(downloading,recording,transcribing,analyzing,clipping)')
$get = "$base/rest/v1/sources?select=id&kind=eq.live&status=in.$estados&stop_requested=eq.false"
$r = Invoke-RestMethod -Uri $get -Headers $headers -TimeoutSec 30
$ids = @($r | ForEach-Object { $_.id })

if ($ids.Count -eq 0) { Write-Output 'No hay directos grabando en este momento.'; return }

$lista = [uri]::EscapeDataString('(' + ($ids -join ',') + ')')
$patchSources = "$base/rest/v1/sources?id=in.$lista"
Invoke-RestMethod -Method Patch -Uri $patchSources -Headers $headers -Body '{"stop_requested":true}' -TimeoutSec 30 | Out-Null

$patchJobs = "$base/rest/v1/jobs?source_id=in.$lista&status=eq.queued"
try { Invoke-RestMethod -Method Patch -Uri $patchJobs -Headers $headers -Body '{"status":"done"}' -TimeoutSec 30 | Out-Null } catch { }

Write-Output "Directos senalados para parar: $($ids.Count)"
Write-Output 'El worker los cierra en unos segundos. Los clips ya grabados se guardan.'
