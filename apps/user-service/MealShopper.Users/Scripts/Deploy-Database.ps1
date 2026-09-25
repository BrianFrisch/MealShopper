<#
.SYNOPSIS
  Compiles and applies modular PostgreSQL schema scripts in deterministic order.
#>
param (
    [string]$ContainerName = "mealshopper-postgres",
    [string]$DbName = "mealshopper",
    [string]$DbUser = "postgres",
    [string]$InitDir = "$PSScriptRoot/../infrastructure/postgres/init"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $InitDir)) {
    throw "Initialization directory not found: $InitDir"
}

Write-Host "Scanning SQL files in: $InitDir" -ForegroundColor Cyan

# Gather all .sql files recursively sorted by directory and filename
$sqlFiles = Get-ChildItem -Path $InitDir -Filter *.sql -Recurse | Sort-Object FullName

$compiledSql = [System.Text.StringBuilder]::new()
[void]$compiledSql.AppendLine("BEGIN;")

foreach ($file in $sqlFiles) {
    Write-Host "  -> Bundling $($file.FullName.Replace((Resolve-Path $InitDir).Path, ''))" -ForegroundColor Gray
    $content = Get-Content -Path $file.FullName -Raw
    [void]$compiledSql.AppendLine("-- FILE: $($file.Name)")
    [void]$compiledSql.AppendLine($content)
    [void]$compiledSql.AppendLine()
}

[void]$compiledSql.AppendLine("COMMIT;")

Write-Host "Applying compiled schema transaction to container '$ContainerName'..." -ForegroundColor Cyan

$compiledSql.ToString() | docker exec -i $ContainerName psql -U $DbUser -d $DbName

if ($LASTEXITCODE -eq 0) {
    Write-Host "Database migration completed successfully!" -ForegroundColor Green
} else {
    Write-Host "Database migration failed with exit code $LASTEXITCODE." -ForegroundColor Red
    exit 1
}