using System.Net.Http.Json;
using System.Text.Json;
using MealShopper.Orchestrator.Exceptions;
using MealShopper.Orchestrator.Models.Shopper;
using Microsoft.Extensions.Logging;

namespace MealShopper.Orchestrator.Clients;

/// <summary>
/// Typed HTTP client implementation for communicating with the Python Shopper Domain service.
/// </summary>
public class ShopperClient : IShopperClient
{
    private readonly HttpClient _httpClient;
    private readonly ILogger<ShopperClient> _logger;

    public ShopperClient(HttpClient httpClient, ILogger<ShopperClient> logger)
    {
        _httpClient = httpClient ?? throw new ArgumentNullException(nameof(httpClient));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    /// <inheritdoc />
    public async Task<List<DiscoveredStore>> DiscoverStoresAsync(
        double lat,
        double lon,
        int radiusMiles,
        int maxStores,
        CancellationToken ct = default)
    {
        var request = new StoreDiscoveryRequest
        {
            Latitude = lat,
            Longitude = lon,
            RadiusMiles = radiusMiles,
            MaxStores = maxStores
        };

        _logger.LogInformation(
            "Sending store discovery request to Shopper Domain. Lat: {Latitude}, Lon: {Longitude}, Radius: {RadiusMiles}, MaxStores: {MaxStores}",
            lat, lon, radiusMiles, maxStores);

        try
        {
            using var response = await _httpClient.PostAsJsonAsync("v1/shopper/stores", request, ct);

            if (!response.IsSuccessStatusCode)
            {
                var errorBody = await response.Content.ReadAsStringAsync(ct);
                _logger.LogError(
                    "Shopper Domain store discovery failed with status {StatusCode}. Response: {ResponseBody}",
                    response.StatusCode, errorBody);

                throw new ShopperDomainException(
                    $"Shopper Domain returned status code {(int)response.StatusCode} ({response.StatusCode}): {errorBody}",
                    response.StatusCode,
                    errorBody);
            }

            var result = await response.Content.ReadFromJsonAsync<StoreDiscoveryResponse>(cancellationToken: ct);
            return result?.Stores ?? [];
        }
        catch (HttpRequestException ex)
        {
            _logger.LogError(ex, "HTTP request error occurred while communicating with Shopper Domain store discovery endpoint.");
            throw new ShopperDomainException("Failed to communicate with Shopper Domain service.", ex);
        }
    }

    /// <inheritdoc />
    public async Task<TopDealsResponse> GetTopDealsAsync(
        List<string> storeIds,
        List<string> avoidIngredients,
        CancellationToken ct = default)
    {
        var request = new FetchDealsRequest
        {
            StoreIds = storeIds ?? [],
            ExcludedIngredients = avoidIngredients ?? []
        };

        _logger.LogInformation(
            "Fetching top deals from Shopper Domain for {StoreCount} stores with {AvoidCount} excluded ingredients.",
            request.StoreIds.Count, request.ExcludedIngredients.Count);

        try
        {
            using var response = await _httpClient.PostAsJsonAsync("v1/shopper/deals", request, ct);

            if (!response.IsSuccessStatusCode)
            {
                var errorBody = await response.Content.ReadAsStringAsync(ct);
                _logger.LogError(
                    "Shopper Domain deal retrieval failed with status {StatusCode}. Response: {ResponseBody}",
                    response.StatusCode, errorBody);

                throw new ShopperDomainException(
                    $"Shopper Domain returned status code {(int)response.StatusCode} ({response.StatusCode}): {errorBody}",
                    response.StatusCode,
                    errorBody);
            }

            var result = await response.Content.ReadFromJsonAsync<TopDealsResponse>(cancellationToken: ct);
            return result ?? new TopDealsResponse();
        }
        catch (HttpRequestException ex)
        {
            _logger.LogError(ex, "HTTP request error occurred while communicating with Shopper Domain deals endpoint.");
            throw new ShopperDomainException("Failed to communicate with Shopper Domain service.", ex);
        }
    }
}
