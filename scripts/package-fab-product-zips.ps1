# Packages optional Fab *source sample projects* (full .uproject trees) for local archives or side
# distribution—NOT the RunUAT marketplace plugin zips served on the main site.
#
# For the official plugin drops (same files as Epic Fab uploads for Win64 / UE 5.7), run
#   fab-products\scripts\build-fab-marketplace-drops-ue57.ps1
# then copy into the web app with:
#   .\scripts\sync-fab-plugin-zips-to-web.ps1
# (outputs to apps\web\public\plugin-packages\UE5.7-Win64\)
#
# Each sample zip is self-contained: .uproject, Config/, Source/, Content/, Plugins/<Product>/, LICENSE.
# Build artifacts (Binaries, Intermediate, Saved, DDC) are excluded so downloads stay small.
#
# Usage (from repo root or scripts/):
#   .\scripts\package-fab-product-zips.ps1
#   .\scripts\package-fab-product-zips.ps1 -FabProductsRoot "C:\path\to\fab-products" -OutputDir "...\public\fab-samples"
#
param(
	[string]$FabProductsRoot = "",
	[string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"

$scriptDir = $PSScriptRoot
$repoRoot = Split-Path $scriptDir -Parent

if (-not $FabProductsRoot) {
	$defaultFab = Join-Path (Split-Path $repoRoot -Parent) "fab-products"
	if (Test-Path $defaultFab) {
		$FabProductsRoot = $defaultFab
	} else {
		$FabProductsRoot = Join-Path $repoRoot "..\fab-products"
	}
}

if (-not $OutputDir) {
	$OutputDir = Join-Path $repoRoot "apps\web\public\fab-samples"
}

$FabProductsRoot = (Resolve-Path $FabProductsRoot).Path
$OutputDir = $OutputDir -replace "[/\\]$", ""
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$exclude = @("Binaries", "Intermediate", "Saved", "DerivedDataCache", ".vs")

function Copy-UEProjectForZip {
	param(
		[string]$From,
		[string]$To
	)
	$args = @($From, $To, "/E", "/NFL", "/NDL", "/NJH", "/NJS", "/NS", "/NC")
	foreach ($d in $exclude) {
		$args = $args + @("/XD", $d)
	}
	$rc = & robocopy @args
	if ($rc -ge 8) {
		throw "robocopy failed with exit code $rc ($From -> $To)"
	}
}

function New-FabSampleZip {
	param(
		[string]$SourceRelativePath,
		[string]$TopFolderName,
		[string]$OutFileName,
		[string]$OptionalLicenseFromProductRoot
	)
	$sourceDir = Join-Path $FabProductsRoot $SourceRelativePath
	$temp = Join-Path ([System.IO.Path]::GetTempPath()) ("fab-zip-staging-" + [Guid]::NewGuid().ToString("N"))
	$stageRoot = Join-Path $temp $TopFolderName
	try {
		Copy-UEProjectForZip -From $sourceDir -To $stageRoot
		if ($OptionalLicenseFromProductRoot -and (Test-Path $OptionalLicenseFromProductRoot)) {
			Copy-Item -LiteralPath $OptionalLicenseFromProductRoot -Destination (Join-Path $stageRoot "LICENSE") -Force
		}
		$outPath = Join-Path $OutputDir $OutFileName
		if (Test-Path $outPath) {
			Remove-Item -LiteralPath $outPath -Force
		}
		Compress-Archive -Path $stageRoot -DestinationPath $outPath -CompressionLevel Optimal
		Write-Host "Wrote $outPath"
	} finally {
		Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
	}
}

# Harbor: LICENSE lives next to the suite docs (not in Harbor/ in the repo); zips add it.
# Top folder inside the zip = Harbor (matches .uproject / module; sample C++ project).
New-FabSampleZip -SourceRelativePath "harbor-suite\Harbor" -TopFolderName "Harbor" `
	-OutFileName "harbor-suite-harbor.zip" `
	-OptionalLicenseFromProductRoot (Join-Path $FabProductsRoot "harbor-suite\LICENSE")

# These demos include Plugins/ and LICENSE in-tree (Harbor-style layout).
New-FabSampleZip -SourceRelativePath "level-selection-sets\LevelSelectionSetsDemo" -TopFolderName "LevelSelectionSetsDemo" `
	-OutFileName "level-selection-sets-demo.zip" -OptionalLicenseFromProductRoot $null

New-FabSampleZip -SourceRelativePath "worldbuilder-templates\WorldBuilderTemplatesDemo" -TopFolderName "WorldBuilderTemplatesDemo" `
	-OutFileName "worldbuilder-templates-demo.zip" -OptionalLicenseFromProductRoot $null

New-FabSampleZip -SourceRelativePath "workflow-toolkit\WorkflowToolkitDemo" -TopFolderName "WorkflowToolkitDemo" `
	-OutFileName "workflow-toolkit-demo.zip" -OptionalLicenseFromProductRoot $null

Write-Host "Done. Optional sample zips: $OutputDir (not the main marketplace plugin drops)."
