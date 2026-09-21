using System.Text.Json.Serialization;

namespace MealShopper.Orchestrator.Models.Domain;

public class DealDto
{
    [JsonPropertyName("deal_id")]
    public string DealId { get; set; } = string.Empty;

    [JsonPropertyName("store_id")]
    public string StoreId { get; set; } = string.Empty;

    [JsonPropertyName("store_name")]
    public string StoreName { get; set; } = string.Empty;

    [JsonPropertyName("item_name")]
    public string ItemName { get; set; } = string.Empty;

    [JsonPropertyName("category")]
    public string Category { get; set; } = string.Empty;

    [JsonPropertyName("price")]
    public decimal Price { get; set; }

    [JsonPropertyName("unit")]
    public string Unit { get; set; } = string.Empty;

    [JsonPropertyName("primary_ingredient")]
    public string PrimaryIngredient { get; set; } = string.Empty;

    [JsonPropertyName("deal_score")]
    public double? DealScore { get; set; }
}
