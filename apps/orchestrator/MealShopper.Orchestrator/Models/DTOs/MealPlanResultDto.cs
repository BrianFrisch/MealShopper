namespace MealShopper.Orchestrator.Models.DTOs;

/// <summary>
/// Represents an ingredient formatted for display in the Results Dashboard.
/// </summary>
public class DisplayIngredientDto
{
    /// <summary>
    /// Name of the ingredient.
    /// </summary>
    public string Name { get; set; } = string.Empty;

    /// <summary>
    /// Formatted quantity and unit description (e.g., "1.5 lbs" or "1 bundle").
    /// </summary>
    public string AmountDescription { get; set; } = string.Empty;

    /// <summary>
    /// Name of the store offering the deal, or null for pantry items.
    /// </summary>
    public string? StoreName { get; set; }

    /// <summary>
    /// Formatted deal price description (e.g., "$2.49 / lb"), or null if unavailable.
    /// </summary>
    public string? DealPriceDescription { get; set; }
}

/// <summary>
/// Represents a recipe card formatted for display in the Results Dashboard.
/// </summary>
public class RecipeCardDto
{
    /// <summary>
    /// Title or display name of the recipe.
    /// </summary>
    public string RecipeTitle { get; set; } = string.Empty;

    /// <summary>
    /// Short description or summary of the recipe.
    /// </summary>
    public string Description { get; set; } = string.Empty;

    /// <summary>
    /// URL to a thumbnail image for the recipe (placeholder).
    /// </summary>
    public string? ThumbnailUrl { get; set; }

    /// <summary>
    /// Ingredients that are matched with store deals.
    /// </summary>
    public List<DisplayIngredientDto> IngredientsWithDeals { get; set; } = [];

    /// <summary>
    /// Ingredients assumed to be staples or on-hand pantry items.
    /// </summary>
    public List<DisplayIngredientDto> PantryIngredients { get; set; } = [];

    /// <summary>
    /// Step-by-step cooking preparation instructions.
    /// </summary>
    public List<string> Instructions { get; set; } = [];
}

/// <summary>
/// Represents the compiled meal plan result for the Results Dashboard layout.
/// </summary>
public class MealPlanResultDto
{
    /// <summary>
    /// Unique identifier for the meal plan.
    /// </summary>
    public string MealPlanId { get; set; } = string.Empty;

    /// <summary>
    /// Estimated total cost of all required ingredients across the shopping trip.
    /// </summary>
    public decimal EstimatedTotalTripCost { get; set; }

    /// <summary>
    /// Estimated total travel time in minutes for visiting all required stores.
    /// </summary>
    public int TotalTravelTimeMinutes { get; set; }

    /// <summary>
    /// Names of stores required to purchase the ingredients (e.g., ["Vons", "Grocery Outlet"]).
    /// </summary>
    public List<string> RequiredStores { get; set; } = [];

    /// <summary>
    /// List of recipe cards included in this meal plan.
    /// </summary>
    public List<RecipeCardDto> Recipes { get; set; } = [];
}
