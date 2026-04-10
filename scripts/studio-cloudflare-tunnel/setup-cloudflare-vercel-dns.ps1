#Requires -Version 5.1
<#
.SYNOPSIS
  Add apex + www DNS records in Cloudflare so the marketing site resolves on Vercel.

.DESCRIPTION
  After moving a zone to Cloudflare, only tunnel records (e.g. api) may exist. Without
  A/CNAME for @ and www, the apex does not resolve and browsers show chrome-error pages.

  Defaults match Vercel’s common third-party DNS values; confirm in Vercel → Project →
  Domains → your domain → expected DNS.

  Usage:
    $env:CLOUDFLARE_API_TOKEN = '...'
    .\setup-cloudflare-vercel-dns.ps1
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
  [string] $ApiToken = $env:CLOUDFLARE_API_TOKEN,
  [string] $ZoneName = "immersivelabs.space",
  [string] $ApexA = "76.76.21.21",
  [string] $WwwCnameTarget = "cname.vercel-dns.com"
)

$ErrorActionPreference = "Stop"
$Base = "https://api.cloudflare.com/client/v4"

if (-not $ApiToken) {
  Write-Error "Set CLOUDFLARE_API_TOKEN (Zone DNS Edit for $ZoneName)."
}

$headers = @{
  Authorization = "Bearer $ApiToken"
  "Content-Type"  = "application/json"
}

function Invoke-CfApi {
  param([string] $Method, [string] $Uri, $Body = $null)
  $p = @{ Uri = $Uri; Method = $Method; Headers = $headers }
  if ($null -ne $Body) { $p.Body = ($Body | ConvertTo-Json -Compress -Depth 10) }
  return Invoke-RestMethod @p
}

$zonesResp = Invoke-CfApi -Method GET -Uri "$Base/zones?name=$ZoneName"
if (-not $zonesResp.success -or $zonesResp.result.Count -lt 1) {
  Write-Error "Zone '$ZoneName' not found."
}
$zoneId = $zonesResp.result[0].id
Write-Host "Zone $ZoneName id=$zoneId"

function Ensure-DnsRecord {
  param(
    [string] $Type,
    [string] $Name,
    [string] $Content,
    [bool] $Proxied = $false,
    [string] $Comment
  )
  $fqdn = if ($Name -eq "@") { $ZoneName } else { "$Name.$ZoneName" }
  $list = Invoke-CfApi -Method GET -Uri "$Base/zones/$zoneId/dns_records?type=$Type&name=$fqdn"
  foreach ($ex in @($list.result)) {
    if ($ex.content -eq $Content -and [bool]$ex.proxied -eq $Proxied) {
      Write-Host "Already OK: $Type $Name -> $Content"
      return
    }
    if ($PSCmdlet.ShouldProcess("$Name.$ZoneName", "DELETE $($ex.type) $($ex.content)")) {
      Invoke-CfApi -Method DELETE -Uri "$Base/zones/$zoneId/dns_records/$($ex.id)" | Out-Null
      Write-Host "Removed conflicting $($ex.type) $Name"
    }
  }
  $body = @{
    type    = $Type
    name    = $Name
    content = $Content
    ttl     = 1
    proxied = $Proxied
    comment = $Comment
  }
  if ($PSCmdlet.ShouldProcess("$Name.$ZoneName", "CREATE $Type")) {
    $r = Invoke-CfApi -Method POST -Uri "$Base/zones/$zoneId/dns_records" -Body $body
    if (-not $r.success) { Write-Error ($r.errors | ConvertTo-Json -Compress) }
    Write-Host "Created $Type $Name -> $Content (proxied=$Proxied)"
  }
}

Ensure-DnsRecord -Type "A" -Name "@" -Content $ApexA -Proxied $false -Comment "Vercel apex"
Ensure-DnsRecord -Type "CNAME" -Name "www" -Content $WwwCnameTarget -Proxied $false -Comment "Vercel www"
Write-Host "Done. If Vercel shows a different A or CNAME, edit records in Cloudflare to match."
