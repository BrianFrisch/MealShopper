using System.Text.Json.Serialization;

namespace MealShopper.Orchestrator.Models.Domain;

public class StoreDto
{
    [JsonPropertyName("id")]
    public string Id { get; set; } = string.Empty;

    [JsonPropertyName("store_id")]
    public string StoreId { get => Id; set => Id = value; }

    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;

    [JsonPropertyName("street")]
    public string Street { get; set; } = string.Empty;

    [JsonPropertyName("address")]
    public string Address { get => Street; set => Street = value; }

    [JsonPropertyName("city")]
    public string City { get; set; } = string.Empty;

    [JsonPropertyName("state")]
    public string State { get; set; } = string.Empty;

    [JsonPropertyName("zip_code")]
    public string ZipCode { get; set; } = string.Empty;

    [JsonPropertyName("distance_miles")]
    public double? DistanceMiles { get; set; }
}
