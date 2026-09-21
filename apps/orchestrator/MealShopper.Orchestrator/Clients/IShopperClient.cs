using MealShopper.Orchestrator.Models.Domain;
using MealShopper.Orchestrator.Models.Planner;
using MealShopper.Orchestrator.Models.Shopper;

namespace MealShopper.Orchestrator.Clients;

/// <summary>
/// Client interface for interacting with the Python Shopper Domain service.
/// </summary>
public interface IShopperClient
{
    /// <summary>
    /// Discovers grocery stores within the specified radius and coordinates.
    /// </summary>
    Task<StoreDiscoveryResponse> DiscoverStoresAsync(StoreDiscoveryRequest req, CancellationToken ct = default);

    /// <summary>
    /// Fetches top evaluated deals for the specified stores and ingredient exclusions.
    /// </summary>
    Task<DealScoringResponse> ScoreDealsAsync(DealScoringRequest req, CancellationToken ct = default);

    /// <summary>
    /// Looks up deal matches for missing ingredients across the specified stores.
    /// </summary>
    Task<IngredientMatchResponseDto> MatchIngredientsAsync(IngredientMatchRequestDto req, CancellationToken ct = default);

    #region Legacy Overloads (For backward compatibility)

    /// <summary>
    /// Discovers grocery stores within the specified radius and coordinates (legacy overload).
    /// </summary>
    Task<List<StoreDto>> DiscoverStoresAsync(double lat, double lon, int radiusMiles, int maxStores, CancellationToken ct = default);

    /// <summary>
    /// Fetches top evaluated deals for the specified stores and ingredient exclusions (legacy overload).
    /// </summary>
    Task<TopDealsResponse> GetTopDealsAsync(List<string> storeIds, List<string> avoidIngredients, CancellationToken ct = default);

    /// <summary>
    /// Looks up deal matches for missing ingredients across the specified stores (legacy overload).
    /// </summary>
    Task<List<MatchedIngredientDealDto>> LookupIngredientsAsync(List<string> storeIds, List<MissingIngredientDto> missingIngredients, CancellationToken ct = default);

    #endregion
}
