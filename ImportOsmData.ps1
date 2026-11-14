[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0, HelpMessage = "The grocery chain identifier (e.g. ralphs, aldi, vons, trader-joes)")]
    [string]$ChainId,

    [Parameter(Mandatory = $true, Position = 0, HelpMessage = "The grocery chain name (e.g. ralphs, aldi, vons, trader-joes)")]
    [string]$ChainName,

    [Parameter(Position = 1, HelpMessage = "The target region/state code")]
    [string]$StateName = "CA"
)
$OutputFile = "$($ChainId.ToLower())_$($StateName.ToLower()).geojson"

# ==============================================================================
# OVERPASS QL QUERY CONFIGURATION
# ==============================================================================
# We define the targeted area by state name, then look for supermarkets matching
# the Macey's brand or name tags within that explicit boundary area.
$OverpassQuery = @"
[out:json][timeout:270];
area["name"="$StateName"]["ISO3166-2"~"^US-"]->.searchArea;
(
  nwr["shop"="supermarket"]["brand"~"$ChainName",i](area.searchArea);
  nwr["shop"="supermarket"]["name"~"$ChainName",i](area.searchArea);
);
out center;
"@

$ApiUrl = "https://overpass-api.de/api/interpreter"

# ==============================================================================
# EXECUTE API CALL (Bypassing PowerShell POST-to-GET Redirect Bugs)
# ==============================================================================
Write-Host "Querying Overpass API for $ChainName locations in '$StateName'..." -ForegroundColor Cyan

try {
    # Explicitly URL-encode the string to force a compliant form payload string
    $EscapedQuery = [Uri]::EscapeDataString($OverpassQuery)
    $RawPayload = "data=$EscapedQuery"

    # We use User-Agent headers because Overpass blocks common stock script signatures
    $Headers = @{
        "User-Agent" = "$ChainId Data Extractor/1.0 (PowerShell Spatial Script)"
    }

    # Execute the request by passing the raw URL-encoded string directly to -Body
    $Response = Invoke-RestMethod -Uri $ApiUrl -Method Post -Body $RawPayload -ContentType "application/x-www-form-urlencoded" -Headers $Headers -TimeoutSec 300
    
    if ($null -eq $Response -or $null -eq $Response.elements -or $Response.elements.Count -eq 0) {
        Write-Warning "No locations found for $ChainName matching the state '$StateName'."
        exit
    }

    Write-Host "Received $($Response.elements.Count) elements from OSM. Converting to GeoJSON..." -ForegroundColor Green

    # ==============================================================================
    # PARSE OSM JSON TO STANDARD GEOJSON FEATURECOLLECTION
    # ==============================================================================
    $Features = @()

    foreach ($Element in $Response.elements) {
        # Only extract top-level features (nodes/ways with tags) and skip structural skel references
        if ($null -ne $Element.tags) {
            
            # Extract coordinates depending on whether it's a single Node or a Way/Area center
            $Lon = $null
            $Lat = $null
            if ($null -ne $Element.lon) {
                $Lon = $Element.lon
                $Lat = $Element.lat
            } elseif ($null -ne $Element.center) {
                $Lon = $Element.center.lon
                $Lat = $Element.center.lat
            }

            # If coordinate points exist, map them to a standard GeoJSON Feature object
            if ($null -ne $Lon -and $null -ne $Lat) {
                $Feature = [ordered]@{
                    type       = "Feature"
                    geometry   = [ordered]@{
                        type        = "Point"
                        coordinates = @([double]$Lon, [double]$Lat)
                    }
                    properties = $Element.tags
                }
                # Inject the native OSM structural ID back into the properties payload
                $Feature.properties | Add-Member -NotePropertyName "osm_id" -NotePropertyValue $Element.id -Force
                $Features += $Feature
            }
        }
    }

    # Wrap the features inside a native FeatureCollection structure
    $GeoJsonOutput = [ordered]@{
        type     = "FeatureCollection"
        features = $Features
    }

    # Convert the structured data to a clean JSON payload and commit it to disk
    $GeoJsonString = $GeoJsonOutput | ConvertTo-Json -Depth 100
    Set-Content -Path $OutputFile -Value $GeoJsonString -Encoding utf8

    Write-Host "Successfully saved GeoJSON dataset to: $OutputFile" -ForegroundColor Green
}
catch {
    Write-Error "Failed to query Overpass API or parse data. Details: $_ "
}
