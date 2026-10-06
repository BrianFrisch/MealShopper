using System.Text.Json.Serialization;
using MealShopper.Orchestrator.Models.Domain;
using MealShopper.Orchestrator.Models.Shopper;

namespace MealShopper.Orchestrator.Models.DTOs;

/// <summary>
/// Represents the result of a deal discovery job containing discovered stores and their available deals.
/// </summary>
public class DiscoveryResultDto
{
    /// <summary>
    /// List of grocery stores discovered in the requested radius.
    /// </summary>
    [JsonPropertyName("stores")]
    public List<StoreDto> Stores { get; set; } = [];

    /// <summary>
    /// List of evaluated deals available across the discovered stores.
    /// </summary>
    [JsonPropertyName("deals")]
    public List<DealItemDto> Deals { get; set; } = [];
}
