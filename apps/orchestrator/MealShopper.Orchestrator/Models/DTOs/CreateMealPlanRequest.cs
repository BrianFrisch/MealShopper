using System.ComponentModel.DataAnnotations;

namespace MealShopper.Orchestrator.Models.DTOs;

/// <summary>
/// Represents the intake request payload for creating a meal plan based on user preferences and location.
/// </summary>
public class CreateMealPlanRequest : MealPlanDiscoveryRequest
{
    /// <summary>
    /// Preferred cuisines (e.g., "Mexican", "Thai").
    /// </summary>
    public List<string> Cuisines { get; set; } = new();

    /// <summary>
    /// Ingredients to avoid or allergies (e.g., "peanuts").
    /// </summary>
    public List<string> AvoidIngredients { get; set; } = new();
}

