using System.Globalization;
using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;
using MealShopper.Orchestrator.Exceptions;
using MealShopper.Orchestrator.Models.DTOs;
using Microsoft.Extensions.Logging;
using StackExchange.Redis;

namespace MealShopper.Orchestrator.Services;

public class CensusGeocodingService : IGeocodingService
{
    private static readonly Dictionary<string, string> StateCodes = new(StringComparer.OrdinalIgnoreCase)
    {
        ["Alabama"] = "AL", ["Alaska"] = "AK", ["Arizona"] = "AZ", ["Arkansas"] = "AR",
        ["California"] = "CA", ["Colorado"] = "CO", ["Connecticut"] = "CT", ["Delaware"] = "DE",
        ["District of Columbia"] = "DC", ["Florida"] = "FL", ["Georgia"] = "GA", ["Hawaii"] = "HI",
        ["Idaho"] = "ID", ["Illinois"] = "IL", ["Indiana"] = "IN", ["Iowa"] = "IA",
        ["Kansas"] = "KS", ["Kentucky"] = "KY", ["Louisiana"] = "LA", ["Maine"] = "ME",
        ["Maryland"] = "MD", ["Massachusetts"] = "MA", ["Michigan"] = "MI", ["Minnesota"] = "MN",
        ["Mississippi"] = "MS", ["Missouri"] = "MO", ["Montana"] = "MT", ["Nebraska"] = "NE",
        ["Nevada"] = "NV", ["New Hampshire"] = "NH", ["New Jersey"] = "NJ", ["New Mexico"] = "NM",
        ["New York"] = "NY", ["North Carolina"] = "NC", ["North Dakota"] = "ND", ["Ohio"] = "OH",
        ["Oklahoma"] = "OK", ["Oregon"] = "OR", ["Pennsylvania"] = "PA", ["Rhode Island"] = "RI",
        ["South Carolina"] = "SC", ["South Dakota"] = "SD", ["Tennessee"] = "TN", ["Texas"] = "TX",
        ["Utah"] = "UT", ["Vermont"] = "VT", ["Virginia"] = "VA", ["Washington"] = "WA",
        ["West Virginia"] = "WV", ["Wisconsin"] = "WI", ["Wyoming"] = "WY",
        ["Puerto Rico"] = "PR", ["Guam"] = "GU", ["American Samoa"] = "AS",
        ["Northern Mariana Islands"] = "MP", ["U.S. Virgin Islands"] = "VI"
    };

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
        var zip = address.ZipCode?.Trim() ?? string.Empty;
        var cacheKey = "geo:cache:v2:" + string.Join(":", new[] { zip, address.Street, address.City, address.State }
            .Select(value => Uri.EscapeDataString(value?.Trim().ToLowerInvariant() ?? string.Empty)));

        var db = _redis.GetDatabase();
        var cached = await db.StringGetAsync(cacheKey);
        if (cached.HasValue)
        {
            var parts = cached.ToString().Split(',');
            if (parts.Length == 2 &&
                double.TryParse(parts[0], NumberStyles.Float, CultureInfo.InvariantCulture, out var cLat) &&
                double.TryParse(parts[1], NumberStyles.Float, CultureInfo.InvariantCulture, out var cLon) &&
                IsValidCoordinates(cLat, cLon))
            {
                _logger.LogInformation("Geocoding cache hit for {CacheKey}: ({Lat}, {Lon})", cacheKey, cLat, cLon);
                return (cLat, cLon);
            }
        }

        var providerFailed = false;
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
            if (match?.Coordinates is { X: not null, Y: not null } coordinates &&
                IsValidCoordinates(coordinates.Y.Value, coordinates.X.Value))
            {
                var lat = coordinates.Y.Value; // Census Y = Latitude
                var lon = coordinates.X.Value; // Census X = Longitude

                _logger.LogInformation("Resolved coordinates for {Street}, {Zip}: ({Lat}, {Lon})", address.Street, zip, lat, lon);

                // Cache for 30 days
                await db.StringSetAsync(cacheKey, FormattableString.Invariant($"{lat},{lon}"), TimeSpan.FromDays(30));
                return (lat, lon);
            }

            _logger.LogWarning("Census Geocoder returned no address match. Trying ZIP code and city/state.");
        }
        catch (Exception ex) when (ex is HttpRequestException or JsonException or TaskCanceledException && !ct.IsCancellationRequested)
        {
            providerFailed = true;
            _logger.LogWarning(ex, "Census Geocoder failed. Trying ZIP code and city/state.");
        }

        var state = address.State?.Trim();
        if (state != null && StateCodes.TryGetValue(state, out var stateCode))
        {
            state = stateCode;
        }
        var paths = new List<(string Path, bool IsZip)>();
        if (!string.IsNullOrWhiteSpace(zip))
        {
            paths.Add(($"us/{Uri.EscapeDataString(zip.Split('-')[0])}", true));
        }
        if (!string.IsNullOrWhiteSpace(address.City) && !string.IsNullOrWhiteSpace(state))
        {
            paths.Add(($"us/{Uri.EscapeDataString(state)}/{Uri.EscapeDataString(address.City.Trim())}", false));
        }

        foreach (var (path, isZip) in paths)
        {
            try
            {
                using var response = await _httpClient.GetAsync($"https://api.zippopotam.us/{path}", ct);
                if (response.StatusCode == HttpStatusCode.NotFound)
                {
                    continue;
                }

                response.EnsureSuccessStatusCode();
                var location = await response.Content.ReadFromJsonAsync<PostalResponse>(cancellationToken: ct);
                var place = location?.Places?.FirstOrDefault(p =>
                    (!isZip || string.IsNullOrWhiteSpace(state) ||
                        string.Equals(p.StateCode, state, StringComparison.OrdinalIgnoreCase)) &&
                    double.TryParse(p.Latitude, NumberStyles.Float, CultureInfo.InvariantCulture, out var lat) &&
                    double.TryParse(p.Longitude, NumberStyles.Float, CultureInfo.InvariantCulture, out var lon) &&
                    IsValidCoordinates(lat, lon));
                if (place != null)
                {
                    var lat = double.Parse(place.Latitude!, CultureInfo.InvariantCulture);
                    var lon = double.Parse(place.Longitude!, CultureInfo.InvariantCulture);
                    _logger.LogInformation("Resolved approximate coordinates using {FallbackType}.",
                        isZip ? "ZIP code" : "city/state");
                    return (lat, lon);
                }
                _logger.LogWarning("Postal geocoder returned no usable coordinates for {FallbackType}.",
                    isZip ? "ZIP code" : "city/state");
            }
            catch (Exception ex) when (ex is HttpRequestException or JsonException or TaskCanceledException && !ct.IsCancellationRequested)
            {
                providerFailed = true;
                _logger.LogWarning(ex, "Postal geocoder lookup failed.");
            }
        }

        throw new DomainException(providerFailed
            ? "Address could not be found because a geocoding service was unavailable. Please check the address and try again."
            : "Address could not be found. Please check the address and try again.");
    }

    private static bool IsValidCoordinates(double lat, double lon) =>
        double.IsFinite(lat) && lat is >= -90 and <= 90 &&
        double.IsFinite(lon) && lon is >= -180 and <= 180;

    private sealed record CensusGeocodeResponse(
        [property: JsonPropertyName("result")] CensusResult? Result);

    private sealed record CensusResult(
        [property: JsonPropertyName("addressMatches")] List<AddressMatch>? AddressMatches);

    private sealed record AddressMatch(
        [property: JsonPropertyName("coordinates")] CensusCoordinates? Coordinates);

    private sealed record CensusCoordinates(
        [property: JsonPropertyName("x")] double? X,
        [property: JsonPropertyName("y")] double? Y);

    private sealed record PostalResponse(
        [property: JsonPropertyName("places")] List<PostalPlace>? Places);

    private sealed record PostalPlace(
        [property: JsonPropertyName("latitude")] string? Latitude,
        [property: JsonPropertyName("longitude")] string? Longitude,
        [property: JsonPropertyName("state abbreviation")] string? StateCode);
}