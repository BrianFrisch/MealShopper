using System.Text.Json.Serialization;

namespace MealShopper.Orchestrator.Models.Domain;

public class MealPlanResponseDto
{
    [JsonPropertyName("plan_id")]
    public string PlanId { get; set; } = string.Empty;

    [JsonPropertyName("meals")]
    public List<PlannedMealDto> Meals { get; set; } = new();

    [JsonPropertyName("missing_primary_ingredients")]
    public List<string> MissingPrimaryIngredients { get; set; } = new();

    [JsonPropertyName("estimated_total_spend")]
    public decimal EstimatedTotalSpend { get; set; }
}
