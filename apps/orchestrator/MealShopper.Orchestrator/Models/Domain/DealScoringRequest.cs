using System.Text.Json.Serialization;

namespace MealShopper.Orchestrator.Models.Domain;

public class DealScoringRequest
{
    [JsonPropertyName("store_ids")]
    public List<string> StoreIds { get; set; } = new();

    [JsonPropertyName("avoid_ingredients")]
    public List<string> AvoidIngredients { get; set; } = new();

    [JsonPropertyName("top_n")]
    public int TopN { get; set; }
}
