using System.ComponentModel.DataAnnotations;

namespace MealShopper.Orchestrator.Models.DTOs;

public class ConfirmMealPlanRequest
{
    [MinLength(1)]
    public List<string> SelectedRecipeIds { get; set; } = [];
}
