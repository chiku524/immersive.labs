#Requires -Version 5.1
<#
  Start immersive-studio serve on this PC (repo root = STUDIO_REPO_ROOT).
  Usage (from monorepo root):  .\scripts\local-pc-studio\start-studio-api.ps1
#>
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $Root
$env:STUDIO_REPO_ROOT = $Root.Path

$EnvFile = Join-Path $Root "apps\studio-worker\.env.local"
if (Test-Path $EnvFile) {
  Get-Content $EnvFile | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) {
    }
    elseif ($line.Contains("=")) {
      $eq = $line.IndexOf("=")
      if ($eq -ge 1) {
        $key = $line.Substring(0, $eq).Trim()
        $val = $line.Substring($eq + 1).Trim()
        if (
          ($val.StartsWith('"') -and $val.EndsWith('"')) -or
          ($val.StartsWith("'") -and $val.EndsWith("'"))
        ) {
          $val = $val.Substring(1, $val.Length - 2)
        }
        [Environment]::SetEnvironmentVariable($key, $val, "Process")
      }
    }
  }
  Write-Host "Loaded $EnvFile"
} else {
  Write-Host "No $EnvFile — create it from scripts/local-pc-studio/env.studio-worker.local.template"
}

$venvPy = Join-Path $Root "apps\studio-worker\.venv\Scripts\python.exe"
if (Test-Path $venvPy) {
  $pyExe = $venvPy
} else {
  $py = Get-Command python -ErrorAction SilentlyContinue
  if (-not $py) {
    Write-Error "python not found. Create a venv under apps/studio-worker/.venv and pip install -e apps/studio-worker[dev], or install Python 3.11+ on PATH."
  }
  $pyExe = $py.Source
}
Write-Host "STUDIO_REPO_ROOT=$($env:STUDIO_REPO_ROOT)"
Write-Host "Using Python: $pyExe"
Write-Host "Starting immersive-studio serve on http://127.0.0.1:8787 ..."
& $pyExe -m studio_worker.cli serve --host 127.0.0.1 --port 8787
