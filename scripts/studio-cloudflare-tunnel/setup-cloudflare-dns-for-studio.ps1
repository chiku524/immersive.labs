#Requires -Version 5.1
<#
.SYNOPSIS
  Create Cloudflare DNS for api.<zone> -> <tunnel-id>.cfargotunnel.com.

.DESCRIPTION
  cloudflared tunnel route dns can pick the wrong zone when multiple zones exist; this script
  targets the zone by exact name via the Cloudflare API.

  By default the CNAME is **proxied (orange cloud)** so public resolvers return Cloudflare IPv4/IPv6.
  A **DNS-only** CNAME to *.cfargotunnel.com often chains to no public A record, which breaks
  IPv4-only clients (e.g. curl on Windows). Use -Proxied:$false only if you know you need grey cloud.

  Prerequisites:
  1. immersivelabs.space (or your -ZoneName) is added to the SAME Cloudflare account as the tunnel.
  2. Domain uses Cloudflare nameservers (zone status "active"). Until NS point to Cloudflare,
     records edited here will not be used for public DNS.

  API token (create at https://dash.cloudflare.com/profile/api-tokens ):
  - Permissions: Zone > DNS > Edit
  - Zone resources: Include > Specific zone > immersivelabs.space (or All zones)

  Usage:
    $env:CLOUDFLARE_API_TOKEN = 'your_token'
    .\setup-cloudflare-dns-for-studio.ps1

    # ComfyUI hostname (same tunnel id): same token, different -ApiHost
    .\setup-cloudflare-dns-for-studio.ps1 -ApiHost comfy

    .\setup-cloudflare-dns-for-studio.ps1 -ApiToken 'your_token' -WhatIf

#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
  [string] $ApiToken = $env:CLOUDFLARE_API_TOKEN,
  [string] $ZoneName = "immersivelabs.space",
  [string] $ApiHost = "api",
  [string] $TunnelId = "52513248-a776-4f3d-b6fb-7e17c3858b2b",
  [bool] $Proxied = $true
)

$ErrorActionPreference = "Stop"
$Base = "https://api.cloudflare.com/client/v4"

if (-not $ApiToken) {
  Write-Error "Set CLOUDFLARE_API_TOKEN or pass -ApiToken. Token needs Zone.DNS.Edit for zone '$ZoneName'."
}

$headers = @{
  Authorization = "Bearer $ApiToken"
  "Content-Type" = "application/json"
}

$cnameTarget = "$TunnelId.cfargotunnel.com"
$recordName = "$ApiHost.$ZoneName"

function Invoke-CfApi {
  param([string]$Method, [string]$Uri, $Body = $null)
  $params = @{ Uri = $Uri; Method = $Method; Headers = $headers }
  if ($null -ne $Body) {
    $params.Body = ($Body | ConvertTo-Json -Compress -Depth 20)
  }
  return Invoke-RestMethod @params
}

Write-Host "Looking up zone '$ZoneName'..."
$zonesResp = Invoke-CfApi -Method GET -Uri "$Base/zones?name=$ZoneName"
if (-not $zonesResp.success -or $zonesResp.result.Count -lt 1) {
  Write-Error "Zone '$ZoneName' not found in this Cloudflare account. Add the site in Cloudflare first."
}
$zone = $zonesResp.result[0]
$zoneId = $zone.id
Write-Host "Zone id: $zoneId  status: $($zone.status)"
if ($zone.status -ne "active") {
  Write-Warning "Zone status is '$($zone.status)'. Public DNS will not use Cloudflare until nameservers point to Cloudflare (status becomes active)."
}

Write-Host "Listing DNS records for name '$recordName'..."
$listUri = "$Base/zones/$zoneId/dns_records?name=$recordName"
$existing = Invoke-CfApi -Method GET -Uri $listUri
$records = @($existing.result)

foreach ($r in $records) {
  $shouldRemove = $r.type -in @("A", "AAAA", "CNAME")
  if (-not $shouldRemove) { continue }
  if ($PSCmdlet.ShouldProcess($r.name, "DELETE $($r.type) DNS record")) {
    $del = Invoke-CfApi -Method DELETE -Uri "$Base/zones/$zoneId/dns_records/$($r.id)"
    if (-not $del.success) { Write-Warning "Delete failed for $($r.id)" }
    else { Write-Host "Deleted $($r.type) $($r.name)" }
  }
}

$body = @{
  type    = "CNAME"
  name    = $ApiHost
  content = $cnameTarget
  ttl     = 1
  proxied = $Proxied
  comment = "immersive.labs studio worker (cloudflared tunnel)"
}

if ($PSCmdlet.ShouldProcess("$ApiHost -> $cnameTarget", "CREATE CNAME")) {
  $mode = if ($Proxied) { "proxied (orange cloud)" } else { "DNS only (grey cloud)" }
  Write-Host "Creating CNAME $recordName -> $cnameTarget ($mode)..."
  $create = Invoke-CfApi -Method POST -Uri "$Base/zones/$zoneId/dns_records" -Body $body
  if (-not $create.success) {
    Write-Error "Create failed: $($create.errors | ConvertTo-Json -Compress)"
  }
  Write-Host "OK: $($create.result | ConvertTo-Json -Compress)"
}

Write-Host ""
Write-Host "Next: remove conflicting 'api' records from Vercel DNS if nameservers still include Vercel."
Write-Host "After NS are Cloudflare-only, wait for propagation then: curl.exe https://$recordName/api/studio/health"
