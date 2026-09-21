$ErrorActionPreference = "Stop"

# Service endpoints
$identityUrl = "http://localhost:5119"
$gatewayUrl  = "http://localhost:5247"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host " 1. Requesting Token from Identity Service" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

$tokenBody = @{
    grant_type = "password"
    email      = "testuser@mealshopper.local"
    password   = "P@ssword123!"
} | ConvertTo-Json

try {
    $tokenResponse = Invoke-RestMethod -Method Post `
        -Uri "http://localhost:5119/v1/auth/token" `
        -ContentType "application/json" `
        -Body $tokenBody

    $accessToken = $tokenResponse.access_token
    Write-Host "[SUCCESS] Acquired Bearer Token!" -ForegroundColor Green
    Write-Host "Expires in: $($tokenResponse.expires_in) seconds" -ForegroundColor Gray
} catch {
    Write-Host "[ERROR] Failed to obtain token from Identity Service: $_" -ForegroundColor Red
    exit 1
}

$authHeaders = @{
    "Authorization" = "Bearer $accessToken"
    # Attempting to inject spoofed headers; Gateway middleware should sanitize these
    "X-User-Id"     = "spoofed-hacker-id"
    "X-User-Roles"  = "SuperAdmin"
}

Write-Host "`n=========================================" -ForegroundColor Cyan
Write-Host " 2. Submitting Meal Plan via API Gateway" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

$intakePayload = @{
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

try {
    $intakeResponse = Invoke-WebRequest -Method Post `
        -Uri "$gatewayUrl/v1/meal-plans" `
        -Headers $authHeaders `
        -ContentType "application/json" `
        -Body $intakePayload

    Write-Host "[SUCCESS] Gateway Accepted Request!" -ForegroundColor Green
    Write-Host "Status Code : $($intakeResponse.StatusCode)" -ForegroundColor Yellow
    Write-Host "Location    : $($intakeResponse.Headers['Location'])" -ForegroundColor Yellow

    $responseBody = $intakeResponse.Content | ConvertFrom-Json
    $jobId = $responseBody.jobId
    Write-Host "Tracked Job : $jobId" -ForegroundColor Gray
} catch {
    Write-Host "[ERROR] Failed submitting request through API Gateway: $_" -ForegroundColor Red
    exit 1
}

Write-Host "`n=========================================" -ForegroundColor Cyan
Write-Host " 3. Polling Task Status via API Gateway" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

$pollUrl = "http://localhost:5247/v1/tasks/$jobId"
$maxAttempts = 30
$attempt = 1

while ($attempt -le $maxAttempts) {
    try {
        $task = Invoke-RestMethod -Method Get -Uri $pollUrl -Headers $authHeaders
        Write-Host "Attempt $attempt : Status = [$($task.status)] | Stage = '$($task.stageDescription)'" -ForegroundColor White

        if ($task.status -eq "Completed") {
            Write-Host "`n[COMPLETE] Meal Plan Successfully Assembled!" -ForegroundColor Green
            Write-Host "`n========================================================" -ForegroundColor Cyan
            Write-Host "                MEAL PLAN WORKFLOW RESULT               " -ForegroundColor Cyan
            Write-Host "========================================================" -ForegroundColor Cyan
            Write-Host "Plan ID               : $($task.result.mealPlanId)"
            Write-Host "Total Travel Time     : $($task.result.totalTravelTimeMinutes) mins"
            Write-Host "Estimated Total Cost  : $($task.result.estimatedTotalTripCost)"

            Write-Host "`n--------------------------------------------------------" -ForegroundColor DarkGray
            Write-Host "REQUIRED STORES" -ForegroundColor Yellow
            Write-Host "--------------------------------------------------------" -ForegroundColor DarkGray
            foreach ($store in $task.result.requiredStores) {
                Write-Host "  * $store" -ForegroundColor White
            }

            Write-Host "`n--------------------------------------------------------" -ForegroundColor DarkGray
            Write-Host "RECIPES & MEAL DETAILS" -ForegroundColor Yellow
            Write-Host "--------------------------------------------------------" -ForegroundColor DarkGray


            $mealIndex = 1
            foreach ($recipe in $task.result.recipes) {
                Write-Host "`n[$mealIndex] $($recipe.recipeTitle)" -ForegroundColor Green
                Write-Host "    Description: $($recipe.description)" -ForegroundColor Gray

                # Promotional / Deal Ingredients
                Write-Host "    Ingredients with Deals:" -ForegroundColor Cyan
                if ($recipe.ingredientsWithDeals -and $recipe.ingredientsWithDeals.Count -gt 0) {
                    foreach ($dealIng in $recipe.ingredientsWithDeals) {
                        $priceText = if ([string]::IsNullOrWhiteSpace($dealIng.dealPriceDescription)) { "" } else { " ($($dealIng.dealPriceDescription))" }
                        $storeText = if ([string]::IsNullOrWhiteSpace($dealIng.storeName)) { "" } else { " @ $($dealIng.storeName)" }
                        Write-Host "      + $($dealIng.amountDescription) $($dealIng.name)$priceText$storeText" -ForegroundColor White
                    }
                } else {
                    Write-Host "      (None)" -ForegroundColor DarkGray
                }

                # Pantry Staples
                Write-Host "    Pantry Ingredients:" -ForegroundColor DarkYellow
                if ($recipe.pantryIngredients -and $recipe.pantryIngredients.Count -gt 0) {
                    foreach ($pantryIng in $recipe.pantryIngredients) {
                        Write-Host "      - $($pantryIng.amountDescription) $($pantryIng.name)" -ForegroundColor DarkGray
                    }
                } else {
                    Write-Host "      (None)" -ForegroundColor DarkGray
                }

                # Preparation Instructions
                Write-Host "    Instructions:" -ForegroundColor Magenta
                if ($recipe.instructions -and $recipe.instructions.Count -gt 0) {
                    $stepIndex = 1
                    foreach ($step in $recipe.instructions) {
                        Write-Host "      $stepIndex.$step" -ForegroundColor Gray
                        $stepIndex++
                    }
                } else {
                    Write-Host "      (No instructions provided)" -ForegroundColor DarkGray
                }

                $mealIndex++
            }


            break
        }

        if ($task.status -eq "Failed") {
            Write-Host "`n[FAILED] Task failed with message: $($task.errorMessage)" -ForegroundColor Red
            break
        }
    } catch {
        Write-Host "[ERROR] Polling failed: $_" -ForegroundColor Red
        break
    }

    Start-Sleep -Seconds 1
    $attempt++
}
