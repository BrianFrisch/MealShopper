using System.ComponentModel.DataAnnotations;

namespace MealShopper.Orchestrator.Models.DTOs;

/// <summary>
/// Intake request payload for generating a meal plan from pre-selected store deals.
/// </summary>
public class MealPlanGenerationRequest : IValidatableObject
{
    public List<string> SelectedStoreIds { get; set; } = [];
    public List<string> SelectedDealIds { get; set; } = [];
    /// <summary>
    /// When provided, a custom recipe is generated around this ingredient and no deals are required.
    /// </summary>
    [MaxLength(200)]
    public string? MainIngredient { get; set; }
    public List<string> Cuisines { get; set; } = [];
    public List<string> DietaryPreferences { get; set; } = [];
    public List<string> AvoidIngredients { get; set; } = [];
    [Range(1, 5)]
    public int DaysCount { get; set; } = 3;
    [Range(1, 8)]
    public int ServingsCount { get; set; } = 4;

    public IEnumerable<ValidationResult> Validate(ValidationContext validationContext)
    {
        if (!string.IsNullOrWhiteSpace(MainIngredient))
        {
            yield break;
        }

        if (SelectedStoreIds.Count == 0)
        {
            yield return new ValidationResult(
                "At least one store is required.", [nameof(SelectedStoreIds)]);
        }

        if (SelectedDealIds.Count == 0)
        {
            yield return new ValidationResult(
                "At least one deal is required.", [nameof(SelectedDealIds)]);
        }
    }
}
