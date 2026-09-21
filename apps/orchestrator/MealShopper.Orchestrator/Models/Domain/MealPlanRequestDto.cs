using System.Text.Json.Serialization;

namespace MealShopper.Orchestrator.Models.Domain;

public class MealPlanRequestDto
{
    [JsonPropertyName("scored_deals")]
    public List<DealDto> ScoredDeals { get; set; } = new();

    [JsonPropertyName("household_size")]
    public int HouseholdSize { get; set; }

    [JsonPropertyName("target_meal_count")]
    public int TargetMealCount { get; set; }

    [JsonPropertyName("preferred_cuisines")]
    public List<string> PreferredCuisines { get; set; } = new();

    [JsonPropertyName("dietary_restrictions")]
    public List<string> DietaryRestrictions { get; set; } = new();

    [JsonPropertyName("avoid_ingredients")]
    public List<string> AvoidIngredients { get; set; } = new();
}
