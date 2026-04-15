# Run on the host where Ollama + studio-worker listen (Windows VM or dev PC).
$Ollama = if ($env:STUDIO_OLLAMA_URL) { $env:STUDIO_OLLAMA_URL.TrimEnd('/') } else { 'http://127.0.0.1:11434' }
$Worker = if ($env:STUDIO_WORKER_HEALTH_URL) { $env:STUDIO_WORKER_HEALTH_URL.TrimEnd('/') } else { 'http://127.0.0.1:8787' }

Write-Host "=== Ollama ($Ollama/api/tags) ===" -ForegroundColor Cyan
try {
  $r = Invoke-WebRequest -Uri "$Ollama/api/tags" -TimeoutSec 8 -UseBasicParsing
  $c = $r.Content
  if ($c.Length -gt 800) { $c = $c.Substring(0, 800) }
  Write-Host $c
} catch {
  Write-Host "(request failed: $($_.Exception.Message))"
}

Write-Host "`n=== Studio worker ($Worker/api/studio/health) ===" -ForegroundColor Cyan
try {
  $r2 = Invoke-WebRequest -Uri "$Worker/api/studio/health" -TimeoutSec 15 -UseBasicParsing
  Write-Host $r2.Content
} catch {
  Write-Host "(request failed: $($_.Exception.Message))"
}

Write-Host "`n=== cloudflared (Windows service) ===" -ForegroundColor Cyan
$svc = Get-Service -Name 'cloudflared' -ErrorAction SilentlyContinue
if ($svc) {
  $svc | Format-Table -AutoSize
} else {
  Write-Host "No service named 'cloudflared'. Check Task Manager or run tunnel from a terminal."
}

Write-Host "`nDone."
