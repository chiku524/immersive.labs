#Requires -Version 5.1
<#
  Upgrade the Immersive Studio desktop worker venv and restart the local API.
  Usage: .\scripts\local-pc-studio\upgrade-desktop-worker.ps1
#>
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$AppDir = Join-Path $env:LOCALAPPDATA "Immersive Studio"
$VenvPy = Join-Path $AppDir "worker-venv\Scripts\python.exe"
$EnvFile = Join-Path $AppDir "worker.env"

if (-not (Test-Path $VenvPy)) {
  Write-Error "Desktop worker venv missing. Run setup-desktop-studio.ps1 or the in-app Run setup first."
}

function Import-DotEnvFile([string]$Path) {
  if (-not (Test-Path $Path)) { return }
  Get-Content $Path | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) { return }
    if ($line -match '^([^=]+)=(.*)$') {
      $key = $Matches[1].Trim()
      $val = $Matches[2].Trim()
      if (($val.StartsWith('"') -and $val.EndsWith('"')) -or ($val.StartsWith("'") -and $val.EndsWith("'"))) {
        $val = $val.Substring(1, $val.Length - 2)
      }
      Set-Item -Path "Env:$key" -Value $val
    }
  }
}

Write-Host "Upgrading immersive-studio in desktop venv ..."
& $VenvPy -m pip install -q -U pip
& $VenvPy -m pip install -q -e "$RepoRoot\apps\studio-worker[dev]"

$conn = Get-NetTCPConnection -LocalPort 8787 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($conn) {
  $apiPid = $conn.OwningProcess
  Write-Host "Stopping existing Studio API (PID $apiPid) ..."
  Stop-Process -Id $apiPid -Force -ErrorAction SilentlyContinue
  Start-Sleep -Seconds 2
}

Import-DotEnvFile $EnvFile
# Never inherit monorepo layout when desktop data dir is configured.
if ($env:STUDIO_WORKER_DATA_DIR) {
  Remove-Item Env:STUDIO_REPO_ROOT -ErrorAction SilentlyContinue
}

$logFile = Join-Path $AppDir "worker-serve.log"
$Pyw = Join-Path $AppDir "worker-venv\Scripts\pythonw.exe"
$Launcher = if (Test-Path $Pyw) { $Pyw } else { $VenvPy }

Write-Host "Starting Studio API on http://127.0.0.1:8787 ..."
$argList = @("-m", "studio_worker.cli", "serve", "--host", "127.0.0.1", "--port", "8787")
Start-Process -FilePath $Launcher `
  -ArgumentList $argList `
  -WorkingDirectory $AppDir `
  -WindowStyle Hidden `
  -RedirectStandardError $logFile

for ($i = 0; $i -lt 30; $i++) {
  Start-Sleep -Seconds 1
  try {
    $r = Invoke-RestMethod -Uri "http://127.0.0.1:8787/api/studio/health" -TimeoutSec 3
    Write-Host "Studio API OK - worker_version $($r.worker_version)" -ForegroundColor Green
    $paths = Invoke-RestMethod -Uri "http://127.0.0.1:8787/api/studio/paths" -TimeoutSec 3
    Write-Host "Jobs root: $($paths.jobs_root)"
    exit 0
  } catch {
    # wait
  }
}

Write-Host "API did not become healthy in 30s. See $logFile" -ForegroundColor Yellow
exit 1
