using System.Text.Json.Serialization;

namespace MealShopper.Orchestrator.Models.Domain;

public class StoreDiscoveryResponse
{
    [JsonPropertyName("stores")]
    public List<StoreDto> Stores { get; set; } = new();

    [JsonPropertyName("total_found")]
    public int TotalFound { get; set; }
}
