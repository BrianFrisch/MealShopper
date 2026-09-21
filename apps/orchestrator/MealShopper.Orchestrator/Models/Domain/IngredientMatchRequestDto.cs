using System.Text.Json.Serialization;

namespace MealShopper.Orchestrator.Models.Domain;

public class IngredientMatchRequestDto
{
    [JsonPropertyName("store_ids")]
    public List<string> StoreIds { get; set; } = new();

    [JsonPropertyName("missing_ingredients")]
    public List<string> MissingIngredients { get; set; } = new();

    [JsonPropertyName("similarity_threshold")]
    public double SimilarityThreshold { get; set; }
}
