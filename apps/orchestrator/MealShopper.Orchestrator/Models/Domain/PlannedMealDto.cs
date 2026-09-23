using System.Text.Json.Serialization;

namespace MealShopper.Orchestrator.Models.Domain;

/// <summary>
/// Represents a planned meal across planning responses, drafts, and consolidated meal plan results.
/// </summary>
public class PlannedMealDto
{
    /// <summary>
    /// Unique identifier for the meal.
    /// </summary>
    [JsonPropertyName("meal_id")]
    public string MealId { get; set; } = string.Empty;

    /// <summary>
    /// Type of meal category (e.g., Breakfast, Lunch, Dinner, Snack, Dessert).
    /// </summary>
    [JsonPropertyName("meal_type")]
    public string MealType { get; set; } = string.Empty;

    /// <summary>
    /// Title or display name of the meal / recipe.
    /// </summary>
    [JsonPropertyName("recipe_title")]
    public string RecipeTitle { get; set; } = string.Empty;

    /// <summary>
    /// Alias property mapping for recipe_name compatibility.
    /// </summary>
    [JsonPropertyName("recipe_name")]
    public string RecipeName
    {
        get => RecipeTitle;
        set => RecipeTitle = value;
    }

    /// <summary>
    /// Short summary of the dish.
    /// </summary>
    [JsonPropertyName("description")]
    public string Description { get; set; } = string.Empty;

    /// <summary>
    /// Estimated preparation time in minutes.
    /// </summary>
    [JsonPropertyName("estimated_prep_time_minutes")]
    public int EstimatedPrepTimeMinutes { get; set; }

    /// <summary>
    /// Target number of servings.
    /// </summary>
    [JsonPropertyName("servings")]
    public int Servings { get; set; }

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
