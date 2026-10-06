using System.Text.Json.Serialization;

namespace MealShopper.Orchestrator.Models.Shopper;

/// <summary>
/// Composite identifier for looking up a specific deal at a store.
/// </summary>
public class DealLookupItemDto
{
    /// <summary>
    /// Unique identifier for the deal.
    /// </summary>
    [JsonPropertyName("deal_id")]
    public string DealId { get; set; } = string.Empty;

    /// <summary>
    /// Identifier of the store offering this deal.
    /// </summary>
    [JsonPropertyName("store_id")]
    public string StoreId { get; set; } = string.Empty;
}

/// <summary>
/// Request payload for batch looking up deals by composite keys.
/// </summary>
public class DealBatchLookupRequest
{
    /// <summary>
    /// List of deal and store composite identifiers to look up.
    /// </summary>
    [JsonPropertyName("items")]
    public List<DealLookupItemDto> Items { get; set; } = [];
}
