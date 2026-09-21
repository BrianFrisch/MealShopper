using System.Text.Json.Serialization;

namespace MealShopper.Orchestrator.Models.Domain;

public class DealScoringResponse
{
    [JsonPropertyName("deals")]
    public List<DealDto> Deals { get; set; } = new();

    [JsonPropertyName("total_scored")]
    public int TotalScored { get; set; }
}
