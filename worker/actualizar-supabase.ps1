# Copia las variables de Supabase desde .env.vercel.txt (al lado de worker/) a los worker/.env.
# No imprime valores: solo dice qué archivos actualizó.
param(
  [string]$Origen = (Join-Path (Split-Path -Parent $PSScriptRoot) '.env.vercel.txt'),
  [string[]]$Destinos = @(
    'C:\Users\nino\Documents\Viral-Clips-1\worker\.env',
    'C:\Users\nino\Documents\viral clip 2.0\worker\.env'
  )
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $Origen)) { throw "No existe $Origen" }

$vals = @{}
foreach ($line in Get-Content -LiteralPath $Origen) {
  if ($line -match '^\s*([A-Z0-9_]+)\s*=\s*(.*)$') {
    $k = $Matches[1]
    $v = $Matches[2].Trim()
    if ($v.StartsWith('"') -or $v.StartsWith("'")) { $v = $v.Trim('"').Trim("'") }
    $vals[$k] = $v
  }
}

$url  = $vals['NEXT_PUBLIC_SUPABASE_URL']; if (-not $url)  { $url = $vals['SUPABASE_URL'] }
$anon = $vals['NEXT_PUBLIC_SUPABASE_ANON_KEY']; if (-not $anon) { $anon = $vals['NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY'] }
$svc  = $vals['SUPABASE_SERVICE_ROLE_KEY']; if (-not $svc) { $svc = $vals['SUPABASE_SECRET_KEY'] }

if (-not $url -or -not $anon -or -not $svc) {
  throw 'Faltan NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY o SUPABASE_SERVICE_ROLE_KEY en .env.vercel.txt'
}

$map = [ordered]@{
  'SUPABASE_URL'                = $url
  'NEXT_PUBLIC_SUPABASE_URL'    = $url
  'SUPABASE_SERVICE_ROLE_KEY'   = $svc
  'NEXT_PUBLIC_SUPABASE_ANON_KEY' = $anon
}

foreach ($d in $Destinos) {
  if (-not (Test-Path -LiteralPath $d)) { Write-Output "NO EXISTE: $d"; continue }
  $lines = @(Get-Content -LiteralPath $d)
  foreach ($k in $map.Keys) {
    $pat = '^\s*' + [regex]::Escape($k) + '\s*='
    $found = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
      if ($lines[$i] -match $pat) { $lines[$i] = "$k=$($map[$k])"; $found = $true; break }
    }
    if (-not $found) { $lines += "$k=$($map[$k])" }
  }
  [System.IO.File]::WriteAllLines($d, $lines, (New-Object System.Text.UTF8Encoding($false)))
  Write-Output "ACTUALIZADO: $d"
}

Write-Output 'Listo. No se mostraron valores.'
