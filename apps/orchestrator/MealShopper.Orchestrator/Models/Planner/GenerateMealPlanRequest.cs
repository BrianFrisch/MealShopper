using System.Text.Json.Serialization;
using MealShopper.Orchestrator.Models.Shopper;

namespace MealShopper.Orchestrator.Models.Planner;

/// <summary>
/// Request payload sent to the Planning Domain service to generate a meal plan.
/// </summary>
public class GenerateMealPlanRequest
{
    /// <summary>
    /// List of preferred cuisine types (e.g., Italian, Mexican, Asian).
    /// </summary>
    [JsonPropertyName("cuisines")]
    public List<string> Cuisines { get; set; } = [];

    /// <summary>
    /// List of ingredients to avoid due to dietary restrictions or preferences.
    /// </summary>
    [JsonPropertyName("avoid_ingredients")]
    public List<string> AvoidIngredients { get; set; } = [];

    /// <summary>
    /// Top evaluated promotional deals from regional grocery stores to optimize meal recipes around.
    /// </summary>
    [JsonPropertyName("top_deals")]
    public List<DealItemDto> TopDeals { get; set; } = [];

    /// <summary>
    /// Number of days to generate the meal plan for (default: 3).
    /// </summary>
    [JsonPropertyName("days_count")]
    public int DaysCount { get; set; } = 3;
}
