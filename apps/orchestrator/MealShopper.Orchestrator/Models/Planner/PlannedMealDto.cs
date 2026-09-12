using System.Text.Json.Serialization;

namespace MealShopper.Orchestrator.Models.Planner;

/// <summary>
/// Represents an ingredient required for a planned recipe, optionally matched with a promotional deal.
/// </summary>
public class RecipeIngredientDto
{
    /// <summary>
    /// Ingredient name.
    /// </summary>
    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;

    /// <summary>
    /// Numeric quantity needed.
    /// </summary>
    [JsonPropertyName("quantity")]
    public decimal Quantity { get; set; }

    /// <summary>
    /// Measurement unit (e.g., lbs, oz, cup, tbsp, count).
    /// </summary>
    [JsonPropertyName("unit")]
    public string Unit { get; set; } = string.Empty;

    /// <summary>
    /// Associated deal ID if this ingredient is backed by a promotion.
    /// </summary>
    [JsonPropertyName("deal_id")]
    public string? DealId { get; set; }

    /// <summary>
    /// Name of the store providing the deal price.
    /// </summary>
    [JsonPropertyName("store_name")]
    public string? StoreName { get; set; }

    /// <summary>
    /// Promotional price for the ingredient if sourced from a deal.
    /// </summary>
    [JsonPropertyName("deal_price")]
    public decimal? DealPrice { get; set; }
}

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
    [JsonPropertyName("recipe_title")]
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
