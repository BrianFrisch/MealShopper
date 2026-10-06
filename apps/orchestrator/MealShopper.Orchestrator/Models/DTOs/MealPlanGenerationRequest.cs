namespace MealShopper.Orchestrator.Models.DTOs;

/// <summary>
/// Intake request payload for generating a meal plan from pre-selected store deals.
/// </summary>
public class MealPlanGenerationRequest
{
    public List<string> SelectedStoreIds { get; set; } = [];
    public List<string> SelectedDealIds { get; set; } = [];
    public List<string> Cuisines { get; set; } = [];
    public List<string> AvoidIngredients { get; set; } = [];
    public int DaysCount { get; set; } = 3;
}
