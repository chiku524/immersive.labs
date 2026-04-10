#Requires -Version 5.1
<#
.SYNOPSIS
  Add (import) a domain as a new zone in your Cloudflare account via API.

.DESCRIPTION
  Calls POST https://api.cloudflare.com/client/v4/zones with jump_start so Cloudflare
  can try to copy existing DNS records from your current host.

  This does NOT change nameservers at your registrar or in Vercel — you must set the
  printed Cloudflare nameservers where the domain is registered (e.g. Vercel Domains).

  API token (https://dash.cloudflare.com/profile/api-tokens ):
  - Account > Account Settings > Read  (to list account id if -AccountId omitted)
  - Account > Account Resources > Include > All accounts (or your account)
  - Zone > Zone > Create
  Optional for later DNS edits: Zone > DNS > Edit on this zone

  Usage:
    $env:CLOUDFLARE_API_TOKEN = 'your_token'
    .\import-zone-to-cloudflare.ps1

    .\import-zone-to-cloudflare.ps1 -DomainName "immersivelabs.space" -AccountId "10374f367672f4d19db430601db0926b"
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
  [string] $ApiToken = $env:CLOUDFLARE_API_TOKEN,
  [string] $DomainName = "immersivelabs.space",
  [string] $AccountId = $env:CLOUDFLARE_ACCOUNT_ID
)

$ErrorActionPreference = "Stop"
$Base = "https://api.cloudflare.com/client/v4"

if (-not $ApiToken) {
  Write-Error "Set CLOUDFLARE_API_TOKEN (or pass -ApiToken). Token needs Account read + Zone create. See script header."
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

Write-Host "Checking if zone '$DomainName' already exists..."
$existing = Invoke-CfApi -Method GET -Uri "$Base/zones?name=$DomainName"
if ($existing.success -and $existing.result.Count -gt 0) {
  $z = $existing.result[0]
  Write-Host "Zone already in this account:"
  Write-Host "  id:     $($z.id)"
  Write-Host "  status: $($z.status)"
  Write-Host "  NS:     $($z.name_servers -join ', ')"
  Write-Host ""
  Write-Host "Next: at your registrar (e.g. Vercel -> Domain -> Nameservers), set ONLY these nameservers, then wait for status 'active'."
  exit 0
}

$acctId = $AccountId
if (-not $acctId) {
  Write-Host "Listing Cloudflare accounts (needs Account:Read on token)..."
  $accts = Invoke-CfApi -Method GET -Uri "$Base/accounts?per_page=50"
  if (-not $accts.success -or $accts.result.Count -lt 1) {
    Write-Error "Could not list accounts. Pass -AccountId or set CLOUDFLARE_ACCOUNT_ID. From wrangler: wrangler whoami shows Account ID."
  }
  if ($accts.result.Count -gt 1) {
    Write-Warning "Multiple accounts found; using first: $($accts.result[0].name) ($($accts.result[0].id))). Pass -AccountId to pick another."
  }
  $acctId = $accts.result[0].id
}

Write-Host "Creating zone '$DomainName' in account $acctId (jump_start=true)..."

$body = @{
  name       = $DomainName
  type       = "full"
  jump_start = $true
  account    = @{ id = $acctId }
}

if (-not $PSCmdlet.ShouldProcess($DomainName, "POST /zones (create zone in Cloudflare)")) {
  exit 0
}

$create = Invoke-CfApi -Method POST -Uri "$Base/zones" -Body $body
if (-not $create.success) {
  $err = $create.errors | ConvertTo-Json -Compress
  Write-Error "Create zone failed: $err"
}

$r = $create.result
Write-Host ""
Write-Host "Zone created."
Write-Host "  id:     $($r.id)"
Write-Host "  status: $($r.status)"
Write-Host "  NS:     $($r.name_servers -join ', ')"
Write-Host ""
Write-Host "=== Required manual step (cannot be done via Cloudflare API alone) ==="
Write-Host "1. Open your domain registrar (if the domain uses Vercel: Vercel -> Project/Domains -> immersivelabs.space -> Nameservers)."
Write-Host "2. Replace existing nameservers with EXACTLY these two (Cloudflare-assigned):"
foreach ($ns in $r.name_servers) { Write-Host "     $ns" }
Write-Host "3. Wait until Cloudflare dashboard shows zone status 'active' (often 5-30+ minutes, sometimes up to 24h)."
Write-Host "4. Re-create critical DNS records in Cloudflare if jump_start missed any (mail, apex, www, api tunnel CNAME, etc.)."
Write-Host ""
Write-Host "Then run: .\setup-cloudflare-dns-for-studio.ps1  (with a DNS-edit token) for api -> tunnel CNAME."
