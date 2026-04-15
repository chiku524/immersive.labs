# Append the active Python's user-site Scripts directory to the *User* PATH so
# `immersive-studio.exe` (pip install --user) is found without pip's warning.
param(
  [string]$PythonExe = ""
)

$ErrorActionPreference = "Continue"
$dotSourced = ($MyInvocation.InvocationName -eq '.')

function Stop-Script([int]$code) {
  if ($dotSourced) { return }
  exit $code
}

if ($PythonExe) {
  $py = $PythonExe
} else {
  $cmd = Get-Command python -ErrorAction SilentlyContinue
  if (-not $cmd) {
    Write-Warning "No 'python' on PATH. Re-run with: -PythonExe 'C:\Path\to\python.exe'"
    Stop-Script 1
  }
  $py = $cmd.Source
}

if (-not (Test-Path -LiteralPath $py)) {
  Write-Warning "Python executable not found: $py"
  Stop-Script 1
}

# Windows: user Scripts are versioned (e.g. ...\Python314\Scripts), not ...\Python\Scripts.
$scripts = (
  & $py -c "import sys, sysconfig; s = 'nt_user' if sys.platform == 'win32' else 'posix_user'; print(sysconfig.get_path('scripts', scheme=s))" 2>$null
).Trim()
if (-not $scripts) {
  Write-Warning "Could not resolve user Scripts path from: $py"
  Stop-Script 1
}
if (-not (Test-Path -LiteralPath $scripts)) {
  Write-Warning "User Scripts folder does not exist yet: $scripts (install the package first, e.g. pip install -U immersive-studio)"
  Stop-Script 1
}

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -and ($userPath -like "*${scripts}*")) {
  Write-Host "User PATH already includes: $scripts"
  Stop-Script 0
}

if ($userPath) {
  [Environment]::SetEnvironmentVariable("Path", "$userPath;$scripts", "User")
} else {
  [Environment]::SetEnvironmentVariable("Path", $scripts, "User")
}

$env:Path = "$env:Path;$scripts"
Write-Host "Appended to User PATH: $scripts"
Write-Host "Open a new terminal (or re-login) so other apps see the updated PATH."
Stop-Script 0
