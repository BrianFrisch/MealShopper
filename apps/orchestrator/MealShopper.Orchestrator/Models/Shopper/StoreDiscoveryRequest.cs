using System.Text.Json.Serialization;

namespace MealShopper.Orchestrator.Models.Shopper;

/// <summary>
/// Request payload for discovering grocery stores in a regional proximity.
/// </summary>
public class StoreDiscoveryRequest
{
    /// <summary>
    /// Latitude of the search origin in decimal degrees.
    /// </summary>
    [JsonPropertyName("latitude")]
    public double Latitude { get; set; }

    /// <summary>
    /// Longitude of the search origin in decimal degrees.
    /// </summary>
    [JsonPropertyName("longitude")]
    public double Longitude { get; set; }

    /// <summary>
    /// Search radius in miles.
    /// </summary>
    [JsonPropertyName("radius_miles")]
    public int RadiusMiles { get; set; }

    /// <summary>
    /// Maximum number of stores to return.
    /// </summary>
    [JsonPropertyName("max_stores")]
    public int MaxStores { get; set; }
}
