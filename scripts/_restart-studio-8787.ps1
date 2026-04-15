# Find listener on 8787, stop owning processes, start studio_worker serve.
$ErrorActionPreference = "Continue"
$port = 8787
$root = "C:\Users\chiku\Desktop\vibe-code\immersive.labs\apps\studio-worker"
$py = "C:\Python314\python.exe"

# Ensure pip user Scripts (immersive-studio.exe) is on User PATH for this session + future shells.
. (Join-Path $PSScriptRoot "ensure-immersive-studio-on-path.ps1") -PythonExe $py

function Stop-ListenersOnPort([int]$listenPort) {
  for ($round = 0; $round -lt 4; $round++) {
    $conns = @(Get-NetTCPConnection -LocalPort $listenPort -State Listen -ErrorAction SilentlyContinue)
    if (-not $conns) { return }
    foreach ($c in $conns) {
      $procId = $c.OwningProcess
      $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
      if ($p) {
        Write-Host "Stopping listener PID $procId ($($p.ProcessName))"
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
      } else {
        Write-Host "Port $listenPort shows OwningProcess $procId but process is gone (stale socket); stopping child processes..."
      }
      # Uvicorn / multiprocessing: child may keep the socket after parent PID disappears from Get-Process.
      Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.ParentProcessId -eq $procId } |
        ForEach-Object {
          Write-Host "  Stopping child PID $($_.ProcessId) ($($_.Name))"
          Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }
    Start-Sleep -Seconds 2
  }
}

Stop-ListenersOnPort $port

if (-not (Test-Path $root)) { throw "Missing $root" }
if (-not (Test-Path $py)) { throw "Missing Python at $py" }

Push-Location $root
$envFile = Join-Path $root ".env.local"
if (Test-Path $envFile) {
  Get-Content $envFile | ForEach-Object {
    $line = $_.Trim()
    if ($line.StartsWith("#") -or -not $line) { return }
    $idx = $line.IndexOf("=")
    if ($idx -lt 1) { return }
    $k = $line.Substring(0, $idx).Trim()
    $v = $line.Substring($idx + 1).Trim().Trim("'").Trim('"')
    Set-Item -Path "Env:$k" -Value $v -ErrorAction SilentlyContinue
  }
  Write-Host "Loaded env from .env.local"
}

$outLog = Join-Path $env:TEMP "immersive-studio-serve-out.log"
$errLog = Join-Path $env:TEMP "immersive-studio-serve-err.log"
Write-Host "Starting: $py -m studio_worker.cli serve --host 127.0.0.1 --port $port"
Start-Process -FilePath $py -ArgumentList @(
  "-m", "studio_worker.cli", "serve", "--host", "127.0.0.1", "--port", "$port"
) -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput $outLog -RedirectStandardError $errLog

Start-Sleep -Seconds 4
try {
  $h = Invoke-RestMethod -Uri "http://127.0.0.1:$port/api/studio/health" -TimeoutSec 15
  Write-Host "Health:" ($h | ConvertTo-Json -Compress)
} catch {
  Write-Host "Health check failed: $($_.Exception.Message)"
  Write-Host "--- stderr tail ---"
  if (Test-Path $errLog) { Get-Content $errLog -Tail 30 }
}
Pop-Location
