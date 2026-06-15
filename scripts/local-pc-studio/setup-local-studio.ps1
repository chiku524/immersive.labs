#Requires -Version 5.1
<#
  One-time bootstrap for local-first Studio (no GCE VM).
  From monorepo root:  .\scripts\local-pc-studio\setup-local-studio.ps1

  Creates:
    - apps/studio-worker/.venv + editable install (unless -UseDocker)
    - apps/studio-worker/.env.local (from template, with STUDIO_REPO_ROOT)
    - apps/web/.env.development.local (Vite proxy to 127.0.0.1:8787)

  Optional: -UseDocker  skips venv; use docker-compose.local.yml for the API instead.
#>
param(
  [switch]$UseDocker,
  [switch]$SkipNpm
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $Root

Write-Host "=== Immersive Studio local-first setup ===" -ForegroundColor Cyan
Write-Host "Repo: $($Root.Path)"

$EnvTemplate = Join-Path $Root "scripts\local-pc-studio\env.studio-worker.local.template"
$EnvLocal = Join-Path $Root "apps\studio-worker\.env.local"
if (-not (Test-Path $EnvLocal)) {
  $lines = Get-Content $EnvTemplate | Where-Object { $_ -notmatch '^\s*#?\s*STUDIO_REPO_ROOT=' }
  $repoLine = "STUDIO_REPO_ROOT=$($Root.Path -replace '\\','/')"
  @($repoLine) + $lines | Set-Content -Path $EnvLocal -Encoding utf8
  Write-Host "Created $EnvLocal"
} else {
  Write-Host "Keeping existing $EnvLocal"
}

$WebDevExample = Join-Path $Root "apps\web\.env.development.local.example"
$WebDevLocal = Join-Path $Root "apps\web\.env.development.local"
if (-not (Test-Path $WebDevLocal)) {
  Copy-Item $WebDevExample $WebDevLocal
  Write-Host "Created $WebDevLocal (VITE_STUDIO_API_PROXY=1)"
} else {
  Write-Host "Keeping existing $WebDevLocal"
}

if (-not $UseDocker) {
  $venvPy = Join-Path $Root "apps\studio-worker\.venv\Scripts\python.exe"
  if (-not (Test-Path $venvPy)) {
    Write-Host "Creating Python venv under apps/studio-worker/.venv ..."
    python -m venv (Join-Path $Root "apps\studio-worker\.venv")
    $venvPy = Join-Path $Root "apps\studio-worker\.venv\Scripts\python.exe"
  }
  Write-Host "Installing immersive-studio (editable) ..."
  & $venvPy -m pip install -q -U pip
  & $venvPy -m pip install -q -e "$Root\apps\studio-worker[dev]"
  Write-Host "Python worker ready: $venvPy"
} else {
  Write-Host "Skipping venv (-UseDocker)."
  Write-Host "API: docker compose -f scripts/local-pc-studio/docker-compose.local.yml up --build"
}

if (-not $SkipNpm) {
  if (Test-Path (Join-Path $Root "package.json")) {
    Write-Host "npm install (monorepo root) ..."
    npm install --no-audit --no-fund 2>&1 | Out-Null
  }
}

Write-Host ""
Write-Host "=== Next every session ===" -ForegroundColor Green
Write-Host "1. ComfyUI:     .\scripts\local-pc-studio\start-comfyui.ps1"
if ($UseDocker) {
  Write-Host "2. Studio API:  docker compose -f scripts/local-pc-studio/docker-compose.local.yml up --build"
} else {
  Write-Host "2. Studio API:  .\scripts\local-pc-studio\start-studio-api.ps1"
}
Write-Host "3. Web studio:  npm run dev  then open http://localhost:5173/studio"
Write-Host ""
Write-Host "Optional: ollama pull llama3.2 for real specs when Mock is off"
Write-Host "Retire GCE VM: bash scripts/studio-cloudflare-tunnel/retire-gce-studio-vm.sh"
