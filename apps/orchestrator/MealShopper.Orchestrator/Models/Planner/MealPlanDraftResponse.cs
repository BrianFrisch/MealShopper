using System.Text.Json.Serialization;

namespace MealShopper.Orchestrator.Models.Planner;

/// <summary>
/// Generated meal plan draft payload optimized around regional deals, strictly mapped to meal-plan-draft.schema.json.
/// </summary>
public class MealPlanDraftResponse
{
    /// <summary>
    /// Unique identifier for the generated meal plan draft.
    /// </summary>
    [JsonPropertyName("meal_plan_id")]
    public string MealPlanId { get; set; } = string.Empty;

    /// <summary>
    /// List of meals planned for the schedule.
    /// </summary>
    [JsonPropertyName("meals")]
    public List<PlannedMealDto> Meals { get; set; } = [];

    /// <summary>
    /// Primary ingredients required by recipes that were not covered by available promotional deals.
    /// </summary>
    [JsonPropertyName("missing_primary_ingredients")]
    public List<MissingIngredientDto> MissingPrimaryIngredients { get; set; } = [];
}
