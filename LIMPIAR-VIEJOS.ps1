# Borra los archivos viejos que ya no se usan. Ejecútalo UNA vez dentro de la carpeta del proyecto, después de descomprimir el zip:
#   cd C:\Users\pc\Documents\Viral-Clips
#   powershell -ExecutionPolicy Bypass -File .\LIMPIAR-VIEJOS.ps1
$viejos = @(
  "components\Nav.tsx", "components\PromoBanner.tsx", "app\promo",
  "worker\app", "worker\components", "worker\lib", "worker\supabase",
  "worker\middleware.ts", "worker\next.config.mjs", "worker\package.json", "worker\package-lock.json", "worker\tsconfig.json",
  "worker\www.youtube.com_cookies.txt"
)
foreach ($p in $viejos) {
  if (Test-Path $p) { Remove-Item $p -Recurse -Force; Write-Host "borrado: $p" -ForegroundColor Green }
}
Write-Host "Listo. Tu worker\.env no se tocó." -ForegroundColor Cyan
