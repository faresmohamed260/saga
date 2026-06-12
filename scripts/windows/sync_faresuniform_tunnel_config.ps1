$ErrorActionPreference = "Stop"

function Get-CloudflareTunnelAuth {
    $certPath = "C:\Users\Fares Mohamed\.cloudflared\cert.pem"
    if (-not (Test-Path $certPath)) {
        throw "Cloudflare cert.pem not found at $certPath"
    }

    $payloadBase64 = (Get-Content $certPath | Where-Object { $_ -and ($_ -notmatch 'ARGO TUNNEL TOKEN') }) -join ""
    $json = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($payloadBase64))
    return $json | ConvertFrom-Json
}

$auth = Get-CloudflareTunnelAuth
$accountId = $auth.accountID
$apiToken = $auth.apiToken
$zoneId = $auth.zoneID
$tunnelId = "514872c7-7547-4404-b9a3-726a30c45be3"

$headers = @{
    Authorization = "Bearer $apiToken"
    "Content-Type" = "application/json"
}

$uri = "https://api.cloudflare.com/client/v4/accounts/$accountId/cfd_tunnel/$tunnelId/configurations"
$response = Invoke-RestMethod -Headers $headers -Uri $uri -Method Get
if (-not $response.success) {
    throw "Cloudflare GET tunnel configuration failed."
}

$existingIngress = @($response.result.config.ingress)
$managedHostnames = @(
    "hermes.faresuniform.uk",
    "robotics.faresuniform.uk",
    "jarvis.faresuniform.uk",
    "saga.faresuniform.uk"
)

$preservedIngress = @()
$fallbackRule = $null
foreach ($rule in $existingIngress) {
    if ($rule.hostname -and ($managedHostnames -contains $rule.hostname)) {
        continue
    }
    if (-not $rule.hostname -and $rule.service -eq "http_status:404") {
        $fallbackRule = $rule
        continue
    }
    $preservedIngress += $rule
}

$managedIngress = @(
    @{
        hostname = "hermes.faresuniform.uk"
        service = "http://172.25.108.124:9119"
        originRequest = @{}
    },
    @{
        hostname = "robotics.faresuniform.uk"
        service = "http://localhost:8184"
        originRequest = @{}
    },
    @{
        hostname = "jarvis.faresuniform.uk"
        service = "http://localhost:8010"
        originRequest = @{}
    },
    @{
        hostname = "saga.faresuniform.uk"
        service = "http://localhost:8675"
        originRequest = @{}
    }
)

if (-not $fallbackRule) {
    $fallbackRule = @{ service = "http_status:404" }
}

$body = @{
    config = @{
        ingress = @($preservedIngress + $managedIngress + @($fallbackRule))
        "warp-routing" = @{ enabled = $false }
    }
} | ConvertTo-Json -Depth 10

$update = Invoke-RestMethod -Headers $headers -Uri $uri -Method Put -Body $body
if (-not $update.success) {
    throw "Cloudflare PUT tunnel configuration failed."
}

$tunnelCname = "$tunnelId.cfargotunnel.com"
foreach ($hostname in $managedHostnames) {
    $dnsUri = "https://api.cloudflare.com/client/v4/zones/$zoneId/dns_records?type=CNAME&name=$hostname"
    $dnsLookup = Invoke-RestMethod -Headers $headers -Uri $dnsUri -Method Get
    $recordBody = @{
        type = "CNAME"
        name = $hostname
        content = $tunnelCname
        ttl = 1
        proxied = $true
    } | ConvertTo-Json

    if ($dnsLookup.success -and $dnsLookup.result.Count -gt 0) {
        $recordId = $dnsLookup.result[0].id
        $recordUri = "https://api.cloudflare.com/client/v4/zones/$zoneId/dns_records/$recordId"
        $dnsUpdate = Invoke-RestMethod -Headers $headers -Uri $recordUri -Method Put -Body $recordBody
        if (-not $dnsUpdate.success) {
            throw "Cloudflare DNS update failed for $hostname"
        }
    }
    else {
        $createUri = "https://api.cloudflare.com/client/v4/zones/$zoneId/dns_records"
        $dnsCreate = Invoke-RestMethod -Headers $headers -Uri $createUri -Method Post -Body $recordBody
        if (-not $dnsCreate.success) {
            throw "Cloudflare DNS create failed for $hostname"
        }
    }
}

Write-Host "Updated faresuniform tunnel ingress for hermes, robotics, jarvis, and saga." -ForegroundColor Green
Write-Host "SAGA route -> http://localhost:8675"
