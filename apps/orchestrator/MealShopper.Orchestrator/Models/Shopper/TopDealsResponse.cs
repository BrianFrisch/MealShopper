using System.Text.Json.Serialization;

namespace MealShopper.Orchestrator.Models.Shopper;

/// <summary>
/// Geographic coordinates for the regional center or user location.
/// </summary>
public class CoordinatesDto
{
    /// <summary>
    /// Latitude in decimal degrees (-90 to 90).
    /// </summary>
    [JsonPropertyName("latitude")]
    public double Latitude { get; set; }

    /// <summary>
    /// Longitude in decimal degrees (-180 to 180).
    /// </summary>
    [JsonPropertyName("longitude")]
    public double Longitude { get; set; }
}

/// <summary>
/// Geographical and store scope context for the deals.
/// </summary>
public class RegionContextDto
{
    /// <summary>
    /// Geographic coordinates for the regional center or user location.
    /// </summary>
    [JsonPropertyName("coordinates")]
    public CoordinatesDto Coordinates { get; set; } = new();

    /// <summary>
    /// List of store identifiers included in this regional scope.
    /// </summary>
    [JsonPropertyName("store_ids")]
    public List<string> StoreIds { get; set; } = [];
}

/// <summary>
/// Evaluated deal item for a grocery product.
/// </summary>
public class DealItemDto
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

    /// <summary>
    /// Display name of the grocery store.
    /// </summary>
    [JsonPropertyName("store_name")]
    public string StoreName { get; set; } = string.Empty;

    /// <summary>
    /// Descriptive name of the food item or product.
    /// </summary>
    [JsonPropertyName("item_name")]
    public string ItemName { get; set; } = string.Empty;

    /// <summary>
    /// Standardized product category (e.g., Produce, Dairy, Meat, Seafood, Pantry, Bakery).
    /// </summary>
    [JsonPropertyName("normalized_category")]
    public string NormalizedCategory { get; set; } = string.Empty;

    /// <summary>
    /// Current promotional deal price.
    /// </summary>
    [JsonPropertyName("deal_price")]
    public decimal DealPrice { get; set; }

    /// <summary>
    /// Original non-discounted price if available.
    /// </summary>
    [JsonPropertyName("original_price")]
    public decimal? OriginalPrice { get; set; }

    /// <summary>
    /// Three-letter ISO 4217 currency code (default: USD).
    /// </summary>
    [JsonPropertyName("currency")]
    public string Currency { get; set; } = "USD";

    /// <summary>
    /// Measurement unit for the price (e.g., lb, oz, count, each).
    /// </summary>
    [JsonPropertyName("unit")]
    public string Unit { get; set; } = string.Empty;

    /// <summary>
    /// Evaluated value score on a scale of 1 to 10.
    /// </summary>
    [JsonPropertyName("value_score")]
    public double ValueScore { get; set; }
}

/// <summary>
/// Top evaluated deals payload in a regional context strictly mapped to top-deals.schema.json.
/// </summary>
public class TopDealsResponse
{
    /// <summary>
    /// ISO 8601 timestamp representing when the top deals payload was generated.
    /// </summary>
    [JsonPropertyName("timestamp")]
    public DateTimeOffset Timestamp { get; set; }

    /// <summary>
    /// Geographical and store scope context for the deals.
    /// </summary>
    [JsonPropertyName("region_context")]
    public RegionContextDto RegionContext { get; set; } = new();

    /// <summary>
    /// List of top evaluated deals.
    /// </summary>
    [JsonPropertyName("deals")]
    public List<DealItemDto> Deals { get; set; } = new();
}
