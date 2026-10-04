[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0, HelpMessage = "The grocery chain identifier (e.g. ralphs, aldi, vons, trader-joes)")]
    [string]$ChainId,

    [Parameter(Position = 1, HelpMessage = "The target region/state code")]
    [string]$Region = "CA",

    [Parameter(HelpMessage = "API Gateway Base URL")]
    [string]$GatewayUrl = "http://localhost:5247",

    [Parameter(HelpMessage = "If true, imports all banners for the chain; otherwise filters by primary banner only")]
    [bool]$IncludeAllBrands = $false
)

$ErrorActionPreference = "Stop"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host " 1. Requesting Token via API Gateway" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

$tokenBody = @{
    grant_type = "password"
    email      = "admin@mealshopper.local"
    password   = "AdminP@ssword123!"
} | ConvertTo-Json

try {
    $tokenResponse = Invoke-RestMethod -Method Post `
        -Uri "$GatewayUrl/v1/auth/token" `
        -ContentType "application/json" `
        -Body $tokenBody

    $accessToken = $tokenResponse.access_token
    Write-Host "[SUCCESS] Acquired Bearer Token!" -ForegroundColor Green
    Write-Host "Expires in: $($tokenResponse.expires_in) seconds" -ForegroundColor Gray
} catch {
    Write-Host "[ERROR] Failed to obtain token from Gateway: $_" -ForegroundColor Red
    exit 1
}

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host " 2. Importing Stores: Chain='$ChainId', Region='$Region'" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

$authHeaders = @{
    "Authorization" = "Bearer $accessToken"
    # Attempting to inject spoofed headers; Gateway middleware should sanitize these
    "X-User-Id"     = "spoofed-hacker-id"
    "X-User-Roles"  = "SuperAdmin"
}

$importBody = @{
    chain_id = $ChainId
    region   = $Region
    all_brands = $IncludeAllBrands
} | ConvertTo-Json

try {
    $importResponse = Invoke-RestMethod -Method Post `
        -Uri "$GatewayUrl/v1/admin/stores/import" `
        -Headers $authHeaders `
        -ContentType "application/json" `
        -Body $importBody

    Write-Host "[SUCCESS] Store Import Complete!" -ForegroundColor Green
    $importResponse | Format-List
} catch {
    Write-Host "[ERROR] Store import failed: $_" -ForegroundColor Red
    exit 1
}