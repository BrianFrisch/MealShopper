using System.Text.Json.Serialization;

namespace MealShopper.Orchestrator.Models.Shopper;

/// <summary>
/// Request payload for fetching deals across selected stores with optional ingredient exclusions.
/// </summary>
public class FetchDealsRequest
{
    /// <summary>
    /// List of store identifiers to fetch deals for.
    /// </summary>
    [JsonPropertyName("store_ids")]
    public List<string> StoreIds { get; set; } = [];

    /// <summary>
    /// List of ingredients to exclude from deals.
    /// </summary>
    [JsonPropertyName("excluded_ingredients")]
    public List<string> ExcludedIngredients { get; set; } = [];
}
