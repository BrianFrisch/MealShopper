// using System.Text.Json.Serialization;

// namespace MealShopper.Orchestrator.Models.Shopper;

// /// <summary>
// /// Represents a grocery store discovered within the requested search area.
// /// </summary>
// public class DiscoveredStore
// {
//     /// <summary>
//     /// Unique identifier of the store.
//     /// </summary>
//     [JsonPropertyName("store_id")]
//     public string StoreId { get; set; } = string.Empty;

//     /// <summary>
//     /// Display name of the store.
//     /// </summary>
//     [JsonPropertyName("name")]
//     public string Name { get; set; } = string.Empty;

//     /// <summary>
//     /// Physical address of the store.
//     /// </summary>
//     [JsonPropertyName("address")]
//     public string Address { get; set; } = string.Empty;

//     /// <summary>
//     /// Distance from the search coordinates in miles.
//     /// </summary>
//     [JsonPropertyName("distance_miles")]
//     public double DistanceMiles { get; set; }
// }

// /// <summary>
// /// Response payload containing stores discovered within the search area.
// /// </summary>
// public class StoreDiscoveryResponse
// {
//     /// <summary>
//     /// List of discovered grocery stores.
//     /// </summary>
//     [JsonPropertyName("stores")]
//     public List<DiscoveredStore> Stores { get; set; } = new();
// }
