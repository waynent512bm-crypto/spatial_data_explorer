# Starts backend + frontend for local development (Windows).
#   .\scripts\dev.ps1                                   # synthetic demo data
#   .\scripts\dev.ps1 -H5ad E:\path\to\annotated.h5ad -Platform xenium
param(
    [string]$H5ad = "",
    [ValidateSet("xenium", "merscope", "cosmx", "unknown")]
    [string]$Platform = "xenium",
    [string]$Layer = "",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Root "backend\.venv\Scripts\python.exe"

if (-not (Test-Path $Py)) {
    Write-Host "Creating backend virtualenv..."
    python -m venv (Join-Path $Root "backend\.venv")
    & $Py -m pip install -e "$Root\backend[dev]"
}
if (-not (Test-Path (Join-Path $Root "frontend\node_modules"))) {
    Write-Host "Installing frontend packages..."
    Push-Location (Join-Path $Root "frontend"); npm install; Pop-Location
}
if (-not $H5ad) {
    $H5ad = Join-Path $Root "data\demo\demo_annotated.h5ad"
    if (-not (Test-Path $H5ad)) { & $Py -m sde demo --out (Join-Path $Root "data\demo") }
}

$serveArgs = @("-m", "sde", "serve", "--h5ad", $H5ad, "--platform", $Platform, "--port", $Port)
if ($Layer) { $serveArgs += @("--layer", $Layer) }
$backend = Start-Process -FilePath $Py -ArgumentList $serveArgs -NoNewWindow -PassThru

try {
    $env:SDE_BACKEND = "http://127.0.0.1:$Port"
    Push-Location (Join-Path $Root "frontend")
    npm run dev
} finally {
    Pop-Location
    Stop-Process -Id $backend.Id -ErrorAction SilentlyContinue
}
