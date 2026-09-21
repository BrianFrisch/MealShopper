using System.Text.Json.Serialization;

namespace MealShopper.Orchestrator.Models.Domain;

public class StoreDiscoveryRequest
{
    [JsonPropertyName("latitude")]
    public double Latitude { get; set; }

    [JsonPropertyName("longitude")]
    public double Longitude { get; set; }

    [JsonPropertyName("radius_miles")]
    public double RadiusMiles { get; set; }

    [JsonPropertyName("max_stores")]
    public int MaxStores { get; set; }
}
