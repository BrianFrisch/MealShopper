using System.Text.Json.Serialization;

namespace MealShopper.Orchestrator.Models.Shopper;

/// <summary>
/// Represents a matched deal for a requested ingredient.
/// </summary>
public class MatchedIngredientDealDto
{
    /// <summary>
    /// Name of the matched ingredient.
    /// </summary>
    [JsonPropertyName("ingredient_name")]
    public string IngredientName { get; set; } = string.Empty;

    /// <summary>
    /// Unique identifier for the deal.
    /// </summary>
    [JsonPropertyName("deal_id")]
    public string DealId { get; set; } = string.Empty;

    /// <summary>
    /// Unique identifier of the store offering the deal.
    /// </summary>
    [JsonPropertyName("store_id")]
    public string StoreId { get; set; } = string.Empty;

    /// <summary>
    /// Display name of the store offering the deal.
    /// </summary>
    [JsonPropertyName("store_name")]
    public string StoreName { get; set; } = string.Empty;

    /// <summary>
    /// Promotional or deal price for the ingredient.
    /// </summary>
    [JsonPropertyName("deal_price")]
    public decimal DealPrice { get; set; }

    /// <summary>
    /// Unit of measure for the deal pricing (e.g., lb, oz, count, each).
    /// </summary>
    [JsonPropertyName("unit")]
    public string Unit { get; set; } = string.Empty;
}

/// <summary>
/// Response payload containing matched deals for requested ingredients from Phase 6 loop-back resolution.
/// </summary>
public class IngredientLookupResponse
{
    /// <summary>
    /// List of matched ingredient deals.
    /// </summary>
    [JsonPropertyName("matches")]
    public List<MatchedIngredientDealDto> Matches { get; set; } = [];
}
