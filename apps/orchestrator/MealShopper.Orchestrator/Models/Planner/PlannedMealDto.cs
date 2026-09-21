using System.Text.Json.Serialization;
using MealShopper.Orchestrator.Models.Domain;

namespace MealShopper.Orchestrator.Models.Planner;

/// <summary>
/// Represents a planned meal in the meal plan draft.
/// </summary>
public class PlannedMealDto
{
    /// <summary>
    /// Type of meal category (Breakfast, Lunch, Dinner, Snack, Dessert).
    /// </summary>
    [JsonPropertyName("meal_type")]
    public string MealType { get; set; } = string.Empty;

    /// <summary>
    /// Title or display name of the meal / recipe.
    /// </summary>
    [JsonPropertyName("recipe_name")]
    public string RecipeTitle { get; set; } = string.Empty;

    /// <summary>
    /// Short summary of the dish.
    /// </summary>
    [JsonPropertyName("description")]
    public string Description { get; set; } = string.Empty;

    /// <summary>
    /// Complete list of ingredients required for this meal.
    /// </summary>
    [JsonPropertyName("ingredients")]
    public List<RecipeIngredientDto> Ingredients { get; set; } = [];

    /// <summary>
    /// Ordered list of step-by-step cooking preparation instructions.
    /// </summary>
    [JsonPropertyName("instructions")]
    public List<string> Instructions { get; set; } = [];
}
