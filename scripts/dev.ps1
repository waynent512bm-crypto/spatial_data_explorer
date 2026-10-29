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

# Terminals opened before Node.js was installed keep a stale PATH; reload it from the registry.
$env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [Environment]::GetEnvironmentVariable("Path", "User")
# npm.cmd, not npm.ps1, so a restrictive execution policy can't block it.
$Npm = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
if (-not $Npm -and (Test-Path "$env:ProgramFiles\nodejs\npm.cmd")) { $Npm = "$env:ProgramFiles\nodejs\npm.cmd" }
if (-not $Npm) { throw "npm not found. Install Node.js from https://nodejs.org, then restart VS Code." }

if (-not (Test-Path $Py)) {
    Write-Host "Creating backend virtualenv..."
    python -m venv (Join-Path $Root "backend\.venv")
    & $Py -m pip install -e "$Root\backend[dev]"
}
if (-not (Test-Path (Join-Path $Root "frontend\node_modules"))) {
    Write-Host "Installing frontend packages..."
    Push-Location (Join-Path $Root "frontend"); & $Npm install; Pop-Location
}
if (-not $H5ad) {
    $H5ad = Join-Path $Root "data\demo\demo_annotated.h5ad"
    if (-not (Test-Path $H5ad)) { & $Py -m sde demo --out (Join-Path $Root "data\demo") }
}

foreach ($p in @($Port, 5173)) {
    $busy = Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($busy) {
        throw "Port $p is already in use (PID $($busy.OwningProcess)). An earlier dev server may still be running; " +
              "close it, or stop it with: Stop-Process -Id $($busy.OwningProcess)"
    }
}

# Start-Process joins arguments with spaces, so quote the path (it may contain spaces).
$serveArgs = @("-m", "sde", "serve", "--h5ad", "`"$H5ad`"", "--platform", $Platform, "--port", $Port)
if ($Layer) { $serveArgs += @("--layer", "`"$Layer`"") }
$backend = Start-Process -FilePath $Py -ArgumentList $serveArgs -NoNewWindow -PassThru

try {
    $env:SDE_BACKEND = "http://127.0.0.1:$Port"
    Push-Location (Join-Path $Root "frontend")
    & $Npm run dev
} finally {
    Pop-Location
    Stop-Process -Id $backend.Id -ErrorAction SilentlyContinue
}
