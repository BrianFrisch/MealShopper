using System.Text.Json.Serialization;
using MealShopper.Orchestrator.Models.Domain;

namespace MealShopper.Orchestrator.Models.Shopper;

/// <summary>
/// Response payload containing matched deals from a batch lookup.
/// </summary>
public class DealBatchLookupResponse
{
    /// <summary>
    /// List of matched deals found in the repository.
    /// </summary>
    [JsonPropertyName("deals")]
    public List<DealDto> Deals { get; set; } = [];

    /// <summary>
    /// Total number of matching deals found.
    /// </summary>
    [JsonPropertyName("total_found")]
    public int TotalFound { get; set; }
}
