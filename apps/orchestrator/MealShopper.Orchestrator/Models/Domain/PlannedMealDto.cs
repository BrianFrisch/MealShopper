using System.Text.Json.Serialization;

namespace MealShopper.Orchestrator.Models.Domain;

public class PlannedMealDto
{
    [JsonPropertyName("meal_id")]
    public string MealId { get; set; } = string.Empty;

    [JsonPropertyName("recipe_name")]
    public string RecipeName { get; set; } = string.Empty;

    [JsonPropertyName("description")]
    public string Description { get; set; } = string.Empty;

    [JsonPropertyName("estimated_prep_time_minutes")]
    public int EstimatedPrepTimeMinutes { get; set; }

    [JsonPropertyName("servings")]
    public int Servings { get; set; }

    [JsonPropertyName("ingredients")]
    public List<RecipeIngredientDto> Ingredients { get; set; } = new();

    [JsonPropertyName("instructions")]
    public List<string> Instructions { get; set; } = new();
}
