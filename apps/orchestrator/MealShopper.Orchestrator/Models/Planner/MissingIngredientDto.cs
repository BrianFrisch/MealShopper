using System.Text.Json.Serialization;

namespace MealShopper.Orchestrator.Models.Planner;

/// <summary>
/// Represents a primary ingredient required by recipes that was not covered by available promotional deals.
/// </summary>
public class MissingIngredientDto
{
    /// <summary>
    /// Name of the missing primary ingredient.
    /// </summary>
    [JsonPropertyName("ingredient_name")]
    public string IngredientName { get; set; } = string.Empty;

    /// <summary>
    /// Estimated quantity needed.
    /// </summary>
    [JsonPropertyName("quantity")]
    public decimal Quantity { get; set; }

    /// <summary>
    /// Measurement unit (e.g., lb, oz, count, tbsp).
    /// </summary>
    [JsonPropertyName("unit")]
    public string Unit { get; set; } = string.Empty;

    /// <summary>
    /// Titles of recipes in this plan requiring this ingredient.
    /// </summary>
    [JsonPropertyName("associated_recipe_titles")]
    public List<string> AssociatedRecipeTitles { get; set; } = [];
}
