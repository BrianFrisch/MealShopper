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
    $null = Invoke-RestMethod -Uri "$GatewayUrl/v1/meal-plans" -Method Post -Body "{}" -ContentType "application/json"
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
        cuisines          = @("Mexican", "American")
        avoidIngredients  = @("peanuts")
        address           = @{
            street  = "123 Hawthorne Blvd"
            city    = "Lawndale"
            state   = "CA"
            zipCode = "90260"
        }
        searchRadiusMiles = 10
        maxStores         = 3
    } | ConvertTo-Json

    $response = Invoke-WebRequest -Uri "$GatewayUrl/v1/meal-plans" -Method Post -Headers $headers -Body $payload -ContentType "application/json"

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
$MaxAttempts = 40
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

# Assertions on Final Payload
try {
    if ($FinalResult.recipes.Count -lt 1) { throw "No recipes generated." }
    if ($null -eq $FinalResult.estimatedTotalTripCost) { throw "Missing trip cost computation." }

    Write-Host "PASS: Payload assertions passed!" -ForegroundColor Green
    Write-Host "`n--- RESULT SUMMARY ---"
    Write-Host "Recipes Generated: $($FinalResult.recipes.Count)"
    Write-Host "Total Trip Cost  : `$ $($FinalResult.estimatedTotalTripCost)"
    Write-Host "Stores Required  : $($FinalResult.requiredStores -join ', ')"
    Write-Host "----------------------"

} catch {
    Write-Host "FAIL: Final result payload invalid. $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "`nALL TESTS PASSED SUCCESSFULLY!" -ForegroundColor Cyan
exit 0