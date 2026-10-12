using System.Net.Http.Json;
using System.Text.Json.Serialization;
using MealShopper.Orchestrator.Models.DTOs;
using Microsoft.Extensions.Logging;
using StackExchange.Redis;

namespace MealShopper.Orchestrator.Services;

public class CensusGeocodingService : IGeocodingService
{
    private readonly HttpClient _httpClient;
    private readonly IConnectionMultiplexer _redis;
    private readonly ILogger<CensusGeocodingService> _logger;

    public CensusGeocodingService(
        HttpClient httpClient,
        IConnectionMultiplexer redis,
        ILogger<CensusGeocodingService> logger)
    {
        _httpClient = httpClient;
        _redis = redis;
        _logger = logger;
    }

    public async Task<(double Latitude, double Longitude)> ResolveCoordinatesAsync(
        AddressDto address,
        CancellationToken ct = default)
    {
        // 1. Return immediately if coordinates were already provided
        if (address.Latitude.HasValue && address.Longitude.HasValue)
        {
            return (address.Latitude.Value, address.Longitude.Value);
        }

        // 2. Check Redis Cache
        var normalizedStreet = address.Street?.Trim().ToLowerInvariant() ?? string.Empty;
        var zip = address.ZipCode?.Trim() ?? string.Empty;
        var cacheKey = $"geo:cache:{zip}:{normalizedStreet}";

        var db = _redis.GetDatabase();
        var cached = await db.StringGetAsync(cacheKey);
        if (cached.HasValue)
        {
            var parts = cached.ToString().Split(',');
            if (parts.Length == 2 &&
                double.TryParse(parts[0], out var cLat) &&
                double.TryParse(parts[1], out var cLon))
            {
                _logger.LogInformation("Geocoding cache hit for {CacheKey}: ({Lat}, {Lon})", cacheKey, cLat, cLon);
                return (cLat, cLon);
            }
        }

        // 3. Fallback to US Census Bureau Public API
        try
        {
            var query = $"street={Uri.EscapeDataString(address.Street ?? string.Empty)}" +
                        $"&city={Uri.EscapeDataString(address.City ?? string.Empty)}" +
                        $"&state={Uri.EscapeDataString(address.State ?? string.Empty)}" +
                        $"&zip={Uri.EscapeDataString(address.ZipCode ?? string.Empty)}" +
                        $"&benchmark=Public_AR_Current&format=json";

            var response = await _httpClient.GetFromJsonAsync<CensusGeocodeResponse>(
                $"https://geocoding.geo.census.gov/geocoder/locations/address?{query}",
                ct);

            var match = response?.Result?.AddressMatches?.FirstOrDefault();
            if (match?.Coordinates != null)
            {
                var lat = match.Coordinates.Y; // Census Y = Latitude
                var lon = match.Coordinates.X; // Census X = Longitude

                _logger.LogInformation("Resolved coordinates for {Street}, {Zip}: ({Lat}, {Lon})", address.Street, zip, lat, lon);

                // Cache for 30 days
                await db.StringSetAsync(cacheKey, $"{lat},{lon}", TimeSpan.FromDays(30));
                return (lat, lon);
            }

            _logger.LogWarning("Census Geocoder returned no address match for {Address}. Falling back to default coordinates.", address.Street);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to resolve coordinates from Census Geocoder.");
        }

        // 4. Default Fallback (South Bay / Lawndale benchmark)
        return (33.894893, -118.362658);
    }

    private sealed record CensusGeocodeResponse(
        [property: JsonPropertyName("result")] CensusResult? Result);

    private sealed record CensusResult(
        [property: JsonPropertyName("addressMatches")] List<AddressMatch>? AddressMatches);

    private sealed record AddressMatch(
        [property: JsonPropertyName("coordinates")] CensusCoordinates? Coordinates);

    private sealed record CensusCoordinates(
        [property: JsonPropertyName("x")] double X,
        [property: JsonPropertyName("y")] double Y);
}