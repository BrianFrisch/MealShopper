using MealShopper.Orchestrator.Models.Domain;

namespace MealShopper.Orchestrator.Services;

/// <summary>
/// Workflow input parameters for executing a meal plan generation pipeline.
/// </summary>
public record PlanGenerationWorkflowRequest(
    double Latitude,
    double Longitude,
    double RadiusMiles,
    int MaxStores,
    int HouseholdSize,
    int TargetMealCount,
    List<string> PreferredCuisines,
    List<string> DietaryRestrictions,
    List<string> AvoidIngredients
);

/// <summary>
/// Consolidated result of a meal plan generation workflow.
/// </summary>
public record ConsolidatedMealPlanResult(
    string PlanId,
    List<StoreDto> SelectedStores,
    List<PlannedMealDto> Meals,
    List<MatchedDealDto> MatchedSecondaryDeals,
    decimal EstimatedTotalSpend,
    DateTimeOffset GeneratedAt
);

/// <summary>
/// Service interface for coordinating the end-to-end meal plan generation workflow pipeline.
/// </summary>
public interface IMealPlanOrchestrator
{
    /// <summary>
    /// Executes the consolidated meal plan generation workflow across downstream domain services.
    /// </summary>
    /// <param name="request">Workflow input request containing location and meal planning preferences.</param>
    /// <param name="ct">Cancellation token.</param>
    /// <returns>The consolidated meal plan result.</returns>
    Task<ConsolidatedMealPlanResult> ExecuteWorkflowAsync(PlanGenerationWorkflowRequest request, CancellationToken ct = default);

    /// <summary>
    /// Processes a meal planning job through store discovery, deal evaluation, and menu generation.
    /// </summary>
    /// <param name="jobId">The unique job identifier.</param>
    /// <param name="ct">Cancellation token.</param>
    Task ProcessJobAsync(Guid jobId, CancellationToken ct = default);
}
