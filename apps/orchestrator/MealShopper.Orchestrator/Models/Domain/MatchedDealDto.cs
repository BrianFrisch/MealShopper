using System.Text.Json.Serialization;

namespace MealShopper.Orchestrator.Models.Domain;

public class MatchedDealDto
{
    [JsonPropertyName("missing_ingredient")]
    public string MissingIngredient { get; set; } = string.Empty;

    [JsonPropertyName("deal_id")]
    public string DealId { get; set; } = string.Empty;

    [JsonPropertyName("store_id")]
    public string StoreId { get; set; } = string.Empty;

    [JsonPropertyName("store_name")]
    public string StoreName { get; set; } = string.Empty;

    [JsonPropertyName("item_name")]
    public string ItemName { get; set; } = string.Empty;

    [JsonPropertyName("price")]
    public decimal Price { get; set; }

    [JsonPropertyName("unit")]
    public string Unit { get; set; } = string.Empty;

    [JsonPropertyName("similarity_score")]
    public double SimilarityScore { get; set; }
}
