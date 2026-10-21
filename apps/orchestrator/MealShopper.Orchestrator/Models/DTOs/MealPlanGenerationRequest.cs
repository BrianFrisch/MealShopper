using System.ComponentModel.DataAnnotations;

namespace MealShopper.Orchestrator.Models.DTOs;

/// <summary>
/// Intake request payload for generating a meal plan from pre-selected store deals.
/// </summary>
public class MealPlanGenerationRequest
{
    [MinLength(1)]
    public List<string> SelectedStoreIds { get; set; } = [];
    [MinLength(1)]
    public List<string> SelectedDealIds { get; set; } = [];
    public List<string> Cuisines { get; set; } = [];
    public List<string> DietaryPreferences { get; set; } = [];
    public List<string> AvoidIngredients { get; set; } = [];
    [Range(1, 5)]
    public int DaysCount { get; set; } = 3;
    [Range(1, 8)]
    public int ServingsCount { get; set; } = 4;
}
