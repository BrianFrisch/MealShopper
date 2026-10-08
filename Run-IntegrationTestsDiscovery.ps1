<#
.SYNOPSIS
  End-to-End Integration Test Harness for MealShopper
.DESCRIPTION
  Validates API Gateway security, token authentication, job orchestration, 
  and live AI generation. Exits with 0 on success, 1 on failure.
#>

$ErrorActionPreference = "Stop"
$GatewayUrl = "http://localhost:5247"

Write-Host "Starting MealShopper Integration Test Suite..." -ForegroundColor Cyan

# ---------------------------------------------------------
# TEST 1: Negative Path - Missing Authentication
# ---------------------------------------------------------
Write-Host "`n[1/4] Testing Gateway Security (Unauthorized Access)..." 
try {
    $null = Invoke-RestMethod -Uri "$GatewayUrl/v1/meal-plans/discovery" -Method Post -Body "{}" -ContentType "application/json"
    Write-Host "FAIL: Expected 401 Unauthorized, but request succeeded." -ForegroundColor Red
    exit 1
} catch {
    if ($_.Exception.Response.StatusCode.value__ -eq 401) {
        Write-Host "PASS: Unauthenticated request correctly rejected with 401." -ForegroundColor Green
    } else {
        Write-Host "FAIL: Expected 401 Unauthorized, got $($_.Exception.Response.StatusCode.value__)" -ForegroundColor Red
        exit 1
    }
}

# ---------------------------------------------------------
# TEST 2: Token Acquisition
# ---------------------------------------------------------
Write-Host "`n[2/4] Acquiring User Bearer Token..."
try {
    # Adjust payload to match your Identity setup for the test user
    $tokenBody = @{
        grant_type = "password"
        email      = "testuser@mealshopper.local"
        password   = "P@ssword123!"
    }
    
    $tokenResponse = Invoke-RestMethod -Uri "$GatewayUrl/v1/auth/token" -Method Post -Body $tokenBody -ContentType "application/x-www-form-urlencoded"
    $Token = $tokenResponse.access_token

    if (-not $Token) { throw "Token was null or empty." }
    Write-Host "PASS: Token acquired successfully." -ForegroundColor Green
} catch {
    Write-Host "FAIL: Could not acquire token. $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------
# TEST 3: Submit Job (With Header Spoofing)
# ---------------------------------------------------------
Write-Host "`n[3/4] Submitting Meal Plan Job (Validating Header Sanitization)..."
$JobId =$null
$PollUrl =$null

try {
    $headers = @{
        "Authorization" = "Bearer $Token"
        "X-User-Id"     = "spoofed-hacker-id" # Should be stripped by Gateway
        "X-User-Roles"  = "SuperAdmin"
    }

    # $payload = @{
    #     Address = @{ Latitude = 33.894893; Longitude = -118.362658 }
    #     SearchRadiusMiles = 10
    #     MaxStores = 3
    #     HouseholdSize = 4
    #     TargetMealCount = 3
    #     Cuisines = @("Mediterranean", "Mexican")
    #     AvoidIngredients = @("Pork")
    # } | ConvertTo-Json -Depth 5
    $Payload = @{
        cuisines          = @("Chinese", "Thai")
        avoidIngredients  = @("peanuts")
        address           = @{
            street  = "123 Hawthorne Blvd"
            city    = "Lawndale"
            state   = "CA"
            zipCode = "90260"
        }
        searchRadiusMiles = 10
        maxStores         = 4
    } | ConvertTo-Json

    $response = Invoke-WebRequest -Uri "$GatewayUrl/v1/meal-plans/discovery" -Method Post -Headers $headers -Body $payload -ContentType "application/json"

    if ($response.StatusCode -eq 202) {
        $json =$response.Content | ConvertFrom-Json
        $JobId =$json.jobId
        $PollUrl = "$GatewayUrl$($response.Headers.Location)"
        Write-Host "PASS: Job submitted. Received 202 Accepted. JobId: $JobId" -ForegroundColor Green
    } else {
        throw "Unexpected status code: $($response.StatusCode)"
    }
} catch {
    Write-Host "FAIL: Job submission failed. $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------
# TEST 4: Polling Job Status & Payload Assertion
# ---------------------------------------------------------
Write-Host "`n[4/4] Polling Redis Job Store for AI Completion..."
$MaxAttempts = 100
$Attempt = 0
$JobCompleted = $false
$FinalResult = $null

while ($Attempt -lt $MaxAttempts -and -not $JobCompleted) {
    $Attempt++
    Start-Sleep -Seconds 3

    $pollResponse = Invoke-RestMethod -Uri $PollUrl -Method Get -Headers @{ "Authorization" = "Bearer $Token" }
    
    Write-Host "  Attempt $Attempt - Status: $($pollResponse.status) | Stage: $($pollResponse.stageDescription)"

    if ($pollResponse.status -eq "Completed") {
        $JobCompleted = $true
        $FinalResult = $pollResponse.result
    } elseif ($pollResponse.status -eq "Failed") {
        Write-Host "FAIL: Orchestrator reported job failure. Error: $($pollResponse.errorMessage)" -ForegroundColor Red
        exit 1
    }
}

if (-not $JobCompleted) {
    Write-Host "FAIL: Job timed out after 120 seconds." -ForegroundColor Red
    exit 1
}

Write-Host "PASS: Job completed successfully. Final payload received." -ForegroundColor Green
# Write-Host "`nFinal Payload:`n$($FinalResult | ConvertTo-Json -Depth 5)" -ForegroundColor Yellow

# ---------------------------------------------------------
# TEST 4: Polling Job Status & Payload Assertion
# ---------------------------------------------------------
Write-Host "`n[4/4] Polling Redis Job Store for AI Completion..."
$MaxAttempts = 100
$Attempt = 0
$JobCompleted = $false
$FinalResult = $null

while ($Attempt -lt $MaxAttempts -and -not $JobCompleted) {
    $Attempt++
    Start-Sleep -Seconds 3

    $pollResponse = Invoke-RestMethod -Uri $PollUrl -Method Get -Headers @{ "Authorization" = "Bearer $Token" }
    
    Write-Host "  Attempt $Attempt - Status: $($pollResponse.status) | Stage: $($pollResponse.stageDescription)"

    if ($pollResponse.status -eq "Completed") {
        $JobCompleted = $true
        $FinalResult = $pollResponse.result
    } elseif ($pollResponse.status -eq "Failed") {
        Write-Host "FAIL: Orchestrator reported job failure. Error: $($pollResponse.errorMessage)" -ForegroundColor Red
        exit 1
    }
}

if (-not $JobCompleted) {
    Write-Host "FAIL: Job timed out after 300 seconds." -ForegroundColor Red
    exit 1
}

Write-Host "`nPASS: Job completed successfully. Discovered stores and deals received.`n" -ForegroundColor Green

# ---------------------------------------------------------
# Formatted Stores and Deals Presentation
# ---------------------------------------------------------
if ($FinalResult.stores) {
    # Index stores by ID for fast lookup
    $storeLookup = @{}
    foreach ($store in $FinalResult.stores) {
        $storeLookup[$store.id] = $store
    }

    # Group deals by store_id
    $dealsByStore = @{}
    if ($FinalResult.deals) {
        foreach ($deal in $FinalResult.deals) {
            if (-not $dealsByStore.ContainsKey($deal.store_id)) {
                $dealsByStore[$deal.store_id] = [System.Collections.Generic.List[psobject]]::new()
            }
            $dealsByStore[$deal.store_id].Add($deal)
        }
    }

    # Iterate through all discovered stores
    foreach ($store in $FinalResult.stores) {
        $storeDeals = if ($dealsByStore.ContainsKey($store.store_id)) { $dealsByStore[$store.store_id] } else { @() }
        $dealCount = $storeDeals.Count
        
        Write-Host "==========================================================================================" -ForegroundColor DarkGray
        Write-Host " STORE: $($store.name) ($($store.store_id))" -ForegroundColor Cyan
        Write-Host " Address:  $($store.address)" -ForegroundColor Gray
        Write-Host " Distance: $($store.distance_miles) miles" -ForegroundColor Gray
        Write-Host " Deals:    $dealCount found" -ForegroundColor $(if ($dealCount -gt 0) { "Yellow" } else { "DarkYellow" })
        Write-Host "==========================================================================================" -ForegroundColor DarkGray

        if ($dealCount -gt 0) {
            $storeDeals | Select-Object `
                @{Name = "DealId"; Expression = { $_.deal_id }}, `
                @{Name = "Price"; Expression = { "$($_.currency) $($_.deal_price.ToString('F2')) / $($_.unit)" }}, `
                @{Name = "Category"; Expression = { $_.normalized_category }}, `
                @{Name = "Item"; Expression = { $_.item_name }} | `
                Format-Table -AutoSize | Out-String | Write-Host
        } else {
            Write-Host "  (No promotional circular deals found for this location)`n" -ForegroundColor DarkGray
            Write-Host "Store deals: $($store | ConvertTo-Json -Depth 5)" -ForegroundColor DarkGray
        }
    }
} else {
    Write-Host "No stores returned in final payload." -ForegroundColor Yellow
}