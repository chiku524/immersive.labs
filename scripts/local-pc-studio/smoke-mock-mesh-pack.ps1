#Requires -Version 5.1
<#
  Generate a mock spec + placeholder GLB pack locally (no Ollama, no ComfyUI).
  Usage (from repo root):  .\scripts\local-pc-studio\smoke-mock-mesh-pack.ps1
#>
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $Root
$env:STUDIO_REPO_ROOT = $Root.Path
$env:STUDIO_OLLAMA_DISABLED = "1"

$EnvFile = Join-Path $Root "apps\studio-worker\.env.local"
if (Test-Path $EnvFile) {
  Get-Content $EnvFile | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) { return }
    if ($line.Contains("=")) {
      $eq = $line.IndexOf("=")
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

$venvPy = Join-Path $Root "apps\studio-worker\.venv\Scripts\python.exe"
if (Test-Path $venvPy) {
  $pyExe = $venvPy
} else {
  $py = Get-Command python -ErrorAction SilentlyContinue
  if (-not $py) { throw "python not found - create apps/studio-worker/.venv and pip install -e apps/studio-worker[dev]" }
  $pyExe = $py.Source
}

$prompt = if ($env:SMOKE_PROMPT) { $env:SMOKE_PROMPT } else { "wooden barrel prop for a fantasy tavern game" }
Write-Host "=== smoke-mock-mesh-pack ==="
Write-Host "STUDIO_MESH_PROVIDER=$(if ($env:STUDIO_MESH_PROVIDER) { $env:STUDIO_MESH_PROVIDER } else { 'blender_placeholder' })"
Write-Host "Prompt: $prompt"
Write-Host ""

& $pyExe -m studio_worker.cli run-job `
  --prompt $prompt `
  --category prop `
  --style-preset toon_bold `
  --mock `
  --export-mesh

Write-Host ""
Write-Host "=== Next: Unity import ==="
Write-Host "1. Newest job under apps/studio-worker/output/jobs/"
Write-Host "2. Use pack folder or unzip pack.zip (needs manifest.json)"
Write-Host "3. Unity: Immersive Labs -> Import Studio Pack..."
Write-Host "See packages/studio-unity/README.md"
