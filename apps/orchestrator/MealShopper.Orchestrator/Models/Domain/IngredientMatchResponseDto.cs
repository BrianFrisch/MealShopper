using System.Text.Json.Serialization;

namespace MealShopper.Orchestrator.Models.Domain;

public class IngredientMatchResponseDto
{
    [JsonPropertyName("matches")]
    public List<MatchedDealDto> Matches { get; set; } = new();

    [JsonPropertyName("total_matched")]
    public int TotalMatched { get; set; }
}
