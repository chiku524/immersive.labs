# Copies full RunUAT Fab marketplace zips (UE 5.7 Win64) into the web app public folder
# so /p/plugins/* can link to them. Zips are gitignored; run this after
# fab-products\scripts\build-fab-marketplace-drops-ue57.ps1
#
# Usage (from immersive.labs or scripts/):
#   .\scripts\sync-fab-plugin-zips-to-web.ps1
#   .\scripts\sync-fab-plugin-zips-to-web.ps1 -FabProductsRoot "C:\path\to\fab-products"
#
param(
	[string] $FabProductsRoot = ""
)
$ErrorActionPreference = "Stop"
$scriptDir = $PSScriptRoot
$repoRoot = Split-Path $scriptDir -Parent
if (-not $FabProductsRoot) {
	$defaultFab = Join-Path (Split-Path $repoRoot -Parent) "fab-products"
	if (Test-Path -LiteralPath $defaultFab) {
		$FabProductsRoot = $defaultFab
	} else {
		$FabProductsRoot = Join-Path $repoRoot "..\fab-products"
	}
}
$FabProductsRoot = (Resolve-Path -LiteralPath $FabProductsRoot).Path
$srcDir = Join-Path $FabProductsRoot "fab-marketplace-drops\UE5.7-Win64"
if (-not (Test-Path -LiteralPath $srcDir)) {
	Write-Error "Source folder not found. Build drops first: fab-products\scripts\build-fab-marketplace-drops-ue57.ps1`n  Expected: $srcDir"
}
$destDir = Join-Path $repoRoot "apps\web\public\plugin-packages\UE5.7-Win64"
$null = New-Item -ItemType Directory -Force -Path $destDir
$pattern = "*-UE5.7-Win64.zip"
$zips = Get-ChildItem -LiteralPath $srcDir -Filter $pattern -File
if ($zips.Count -eq 0) {
	Write-Warning "No files matching $pattern in $srcDir"
}
foreach ($z in $zips) {
	$out = Join-Path $destDir $z.Name
	Copy-Item -LiteralPath $z.FullName -Destination $out -Force
	Write-Host "Copied: $($z.Name) -> $out" -ForegroundColor Green
}
Write-Host "Done. Rebuild the web app (npm run build) so Vite includes public assets." -ForegroundColor Cyan
