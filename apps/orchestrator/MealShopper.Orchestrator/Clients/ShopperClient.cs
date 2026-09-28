using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using MealShopper.Orchestrator.Exceptions;
using MealShopper.Orchestrator.Models.Domain;
using MealShopper.Orchestrator.Models.Planner;
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
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    public ShopperClient(HttpClient httpClient, ILogger<ShopperClient> logger)
    {
        _httpClient = httpClient ?? throw new ArgumentNullException(nameof(httpClient));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    /// <inheritdoc />
    public async Task<IReadOnlyList<DealItemDto>> GetDealsForStoreAsync(
        string storeId,
        string? postalCode = null,
        string? chain = null,
        CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(storeId))
        {
            _logger.LogWarning("GetDealsForStoreAsync was called with an empty or whitespace storeId.");
            return Array.Empty<DealItemDto>();
        }

        _logger.LogInformation(
            "Fetching deals for store {StoreId} (PostalCode: {PostalCode}, Chain: {Chain})",
            storeId, postalCode, chain);

        try
        {
            var uri = $"v1/deals/stores/{Uri.EscapeDataString(storeId)}";
            var queryParams = new List<string>();

            if (!string.IsNullOrWhiteSpace(postalCode))
            {
                queryParams.Add($"postal_code={Uri.EscapeDataString(postalCode)}");
            }

            if (!string.IsNullOrWhiteSpace(chain))
            {
                queryParams.Add($"chain={Uri.EscapeDataString(chain)}");
            }

            if (queryParams.Count > 0)
            {
                uri += "?" + string.Join("&", queryParams);
            }

            using var response = await _httpClient.GetAsync(uri, ct);

            if (response.StatusCode == HttpStatusCode.NotFound)
            {
                _logger.LogWarning("No active deals found for store {StoreId} (404 Not Found)", storeId);
                return Array.Empty<DealItemDto>();
            }

            if (!response.IsSuccessStatusCode)
            {
                var errorBody = await response.Content.ReadAsStringAsync(ct);
                _logger.LogError(
                    "Failed to fetch deals for store {StoreId} with status code {StatusCode}. Response: {ResponseBody}",
                    storeId, response.StatusCode, errorBody);
                return Array.Empty<DealItemDto>();
            }

            var data = await response.Content.ReadFromJsonAsync<TopDealsResponse>(JsonOptions, ct);
            return data?.Deals ?? (IReadOnlyList<DealItemDto>)Array.Empty<DealItemDto>();
        }
        catch (HttpRequestException ex)
        {
            _logger.LogError(ex, "HTTP request error occurred while fetching deals for store {StoreId}.", storeId);
            return Array.Empty<DealItemDto>();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Unexpected error occurred while fetching deals for store {StoreId}.", storeId);
            return Array.Empty<DealItemDto>();
        }
    }

    /// <inheritdoc />
    public async Task<TopDealsResponse> GetTopDealsForStoresAsync(IEnumerable<string> storeIds, CancellationToken ct = default)
    {
        var storeList = storeIds?
            .Where(s => !string.IsNullOrWhiteSpace(s))
            .Distinct()
            .ToList() ?? [];

        if (storeList.Count == 0)
        {
            _logger.LogWarning("GetTopDealsForStoresAsync called with empty storeIds.");
            return new TopDealsResponse
            {
                Timestamp = DateTimeOffset.UtcNow,
                RegionContext = new RegionContextDto
                {
                    Coordinates = new CoordinatesDto
                    {
                        Latitude = 33.8895,
                        Longitude = -118.3533
                    },
                    StoreIds = []
                },
                Deals = []
            };
        }

        _logger.LogInformation(
            "Fetching deals concurrently across {StoreCount} stores: {StoreIds}",
            storeList.Count, string.Join(", ", storeList));

        var fetchTasks = storeList.Select(sid => GetDealsForStoreAsync(sid, ct: ct));
        var storeDealsResults = await Task.WhenAll(fetchTasks);

        var allDeals = storeDealsResults.SelectMany(deals => deals).ToList();

        // Deduplicate items by ItemName or CleanName keeping the best price/value score
        var dedupedDeals = allDeals
            .GroupBy(d => !string.IsNullOrWhiteSpace(d.CleanName)
                ? d.CleanName.Trim().ToLowerInvariant()
                : d.ItemName.Trim().ToLowerInvariant())
            .Where(g => !string.IsNullOrWhiteSpace(g.Key))
            .Select(g => g.OrderBy(d => d.DealPrice).ThenByDescending(d => d.ValueScore).First())
            .OrderByDescending(d => d.ValueScore)
            .ToList();

        _logger.LogInformation(
            "Consolidated {TotalDeals} raw deals across {StoreCount} stores into {DedupedCount} top deals.",
            allDeals.Count, storeList.Count, dedupedDeals.Count);

        return new TopDealsResponse
        {
            Timestamp = DateTimeOffset.UtcNow,
            RegionContext = new RegionContextDto
            {
                Coordinates = new CoordinatesDto
                {
                    Latitude = 33.8895,
                    Longitude = -118.3533
                },
                StoreIds = storeList
            },
            Deals = dedupedDeals
        };
    }

    /// <inheritdoc />
    public async Task<StoreDiscoveryResponse> DiscoverStoresAsync(
        StoreDiscoveryRequest req,
        CancellationToken ct = default)
    {
        ArgumentNullException.ThrowIfNull(req);

        _logger.LogInformation(
            "Sending store discovery request. Lat: {Latitude}, Lon: {Longitude}, Radius: {RadiusMiles}, MaxStores: {MaxStores}",
            req.Latitude, req.Longitude, req.RadiusMiles, req.MaxStores);

        try
        {
            using var response = await _httpClient.PostAsJsonAsync("v1/shopper/stores/discover", req, JsonOptions, ct);

            if (!response.IsSuccessStatusCode)
            {
                var errorBody = await response.Content.ReadAsStringAsync(ct);
                _logger.LogError(
                    "Store discovery failed with status {StatusCode}. Response: {ResponseBody}",
                    response.StatusCode, errorBody);

                throw new HttpRequestException(
                    $"Store discovery failed with status code {(int)response.StatusCode} ({response.StatusCode}): {errorBody}",
                    null,
                    response.StatusCode);
            }

            var result = await response.Content.ReadFromJsonAsync<StoreDiscoveryResponse>(JsonOptions, ct);
            return result ?? new StoreDiscoveryResponse();
        }
        catch (HttpRequestException ex)
        {
            _logger.LogError(ex, "HTTP request error occurred during store discovery.");
            throw;
        }
    }

    /// <inheritdoc />
    public async Task<DealScoringResponse> ScoreDealsAsync(
        DealScoringRequest req,
        CancellationToken ct = default)
    {
        ArgumentNullException.ThrowIfNull(req);

        _logger.LogInformation(
            "Sending deal scoring request for {StoreCount} stores with TopN: {TopN}",
            req.StoreIds.Count, req.TopN);

        try
        {
            using var response = await _httpClient.PostAsJsonAsync("v1/shopper/deals/score", req, JsonOptions, ct);

            if (!response.IsSuccessStatusCode)
            {
                var errorBody = await response.Content.ReadAsStringAsync(ct);
                _logger.LogError(
                    "Deal scoring failed with status {StatusCode}. Response: {ResponseBody}",
                    response.StatusCode, errorBody);

                throw new HttpRequestException(
                    $"Deal scoring failed with status code {(int)response.StatusCode} ({response.StatusCode}): {errorBody}",
                    null,
                    response.StatusCode);
            }

            var result = await response.Content.ReadFromJsonAsync<DealScoringResponse>(JsonOptions, ct);
            return result ?? new DealScoringResponse();
        }
        catch (HttpRequestException ex)
        {
            _logger.LogError(ex, "HTTP request error occurred during deal scoring.");
            throw;
        }
    }

    /// <inheritdoc />
    public async Task<IngredientMatchResponseDto> MatchIngredientsAsync(
        IngredientMatchRequestDto req,
        CancellationToken ct = default)
    {
        ArgumentNullException.ThrowIfNull(req);

        _logger.LogInformation(
            "Sending ingredient matching request for {IngredientCount} missing ingredients across {StoreCount} stores with SimilarityThreshold: {SimilarityThreshold}",
            req.MissingIngredients.Count, req.StoreIds.Count, req.SimilarityThreshold);

        try
        {
            using var response = await _httpClient.PostAsJsonAsync("v1/shopper/deals/match", req, JsonOptions, ct);

            if (!response.IsSuccessStatusCode)
            {
                var errorBody = await response.Content.ReadAsStringAsync(ct);
                _logger.LogError(
                    "Ingredient matching failed with status {StatusCode}. Response: {ResponseBody}",
                    response.StatusCode, errorBody);

                throw new HttpRequestException(
                    $"Ingredient matching failed with status code {(int)response.StatusCode} ({response.StatusCode}): {errorBody}",
                    null,
                    response.StatusCode);
            }

            var result = await response.Content.ReadFromJsonAsync<IngredientMatchResponseDto>(JsonOptions, ct);
            return result ?? new IngredientMatchResponseDto();
        }
        catch (HttpRequestException ex)
        {
            _logger.LogError(ex, "HTTP request error occurred during ingredient matching.");
            throw;
        }
    }

    #region Legacy Methods

    /// <inheritdoc />
    public async Task<List<StoreDto>> DiscoverStoresAsync(
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

    /// <inheritdoc />
    public async Task<List<MatchedIngredientDealDto>> LookupIngredientsAsync(
        List<string> storeIds,
        List<MissingIngredientDto> missingIngredients,
        CancellationToken ct = default)
    {
        if (missingIngredients is null || missingIngredients.Count == 0)
        {
            return [];
        }

        var request = new IngredientLookupRequest
        {
            StoreIds = storeIds ?? [],
            Items = missingIngredients.Select(m => new LookupItemDto
            {
                Name = m.IngredientName,
                Quantity = m.Quantity,
                Unit = m.Unit
            }).ToList()
        };

        _logger.LogInformation(
            "Looking up deals for {ItemCount} missing ingredients across {StoreCount} stores in Shopper Domain.",
            request.Items.Count, request.StoreIds.Count);

        try
        {
            using var response = await _httpClient.PostAsJsonAsync("v1/shopper/lookup-ingredients", request, ct);

            if (!response.IsSuccessStatusCode)
            {
                var errorBody = await response.Content.ReadAsStringAsync(ct);
                _logger.LogError(
                    "Shopper Domain ingredient lookup failed with status {StatusCode}. Response: {ResponseBody}",
                    response.StatusCode, errorBody);

                throw new ShopperDomainException(
                    $"Shopper Domain returned status code {(int)response.StatusCode} ({response.StatusCode}): {errorBody}",
                    response.StatusCode,
                    errorBody);
            }

            var result = await response.Content.ReadFromJsonAsync<IngredientLookupResponse>(cancellationToken: ct);

            _logger.LogInformation("Found deals for {ItemCount} ingredients",result?.Matches.Count);

            return result?.Matches ?? [];
        }
        catch (HttpRequestException ex)
        {
            _logger.LogError(ex, "HTTP request error occurred while communicating with Shopper Domain lookup-ingredients endpoint.");
            throw new ShopperDomainException("Failed to communicate with Shopper Domain service.", ex);
        }
    }

    #endregion
}
