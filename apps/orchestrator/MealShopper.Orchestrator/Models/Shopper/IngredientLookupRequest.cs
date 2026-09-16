using System.Text.Json.Serialization;

namespace MealShopper.Orchestrator.Models.Shopper;

/// <summary>
/// Represents an ingredient item to look up for deals across stores.
/// </summary>
public class LookupItemDto
{
    /// <summary>
    /// Name of the ingredient.
    /// </summary>
    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;

    /// <summary>
    /// Numeric quantity needed.
    /// </summary>
    [JsonPropertyName("quantity")]
    public decimal Quantity { get; set; }

    /// <summary>
    /// Measurement unit (e.g., lb, oz, count, tbsp).
    /// </summary>
    [JsonPropertyName("unit")]
    public string Unit { get; set; } = string.Empty;
}

/// <summary>
/// Request payload for looking up missing ingredient deals across specified stores in Phase 6 loop-back resolution.
/// </summary>
public class IngredientLookupRequest
{
    /// <summary>
    /// List of store identifiers to search for ingredient deals.
    /// </summary>
    [JsonPropertyName("store_ids")]
    public List<string> StoreIds { get; set; } = [];

    /// <summary>
    /// List of ingredient items to look up.
    /// </summary>
    [JsonPropertyName("items")]
    public List<LookupItemDto> Items { get; set; } = [];
}
