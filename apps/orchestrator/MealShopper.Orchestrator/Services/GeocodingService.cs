using StackExchange.Redis;

using MealShopper.Orchestrator.Models.DTOs;

namespace MealShopper.Orchestrator.Services;
public class GeocodingService : IGeocodingService
{
    private readonly HttpClient _httpClient;
    private readonly IConnectionMultiplexer _redis;
    private readonly ILogger<GeocodingService> _logger;

    public GeocodingService(HttpClient httpClient, IConnectionMultiplexer redis, ILogger<GeocodingService> logger)
    {
        _httpClient = httpClient;
        _redis = redis;
        _logger = logger;
    }

    public async Task<(double Latitude, double Longitude)> ResolveCoordinatesAsync(AddressDto address, CancellationToken ct = default)
    {
        if (address.Latitude.HasValue && address.Longitude.HasValue)
        {
            return (address.Latitude.Value, address.Longitude.Value);
        }

        var normalizedKey = $"geo:cache:{address.ZipCode}:{address.Street.Trim().ToLowerInvariant()}";
        var db = _redis.GetDatabase();
        var cached = await db.StringGetAsync(normalizedKey);

        if (cached.HasValue)
        {
            var parts = cached.ToString().Split(',');
            return (double.Parse(parts[0]), double.Parse(parts[1]));
        }

        // Call Geocoding Provider (or your Shopper-domain GeoService endpoint)
        var query = $"{address.Street}, {address.City}, {address.State} {address.ZipCode}";
        // ... execute geocode request ...

        var resolvedLat = 33.894893; // provider result
        var resolvedLon = -118.362658;

        // Cache for 30 days
        await db.StringSetAsync(normalizedKey, $"{resolvedLat},{resolvedLon}", TimeSpan.FromDays(30));
        return (resolvedLat, resolvedLon);
    }
}