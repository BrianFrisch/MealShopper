using MealShopper.Orchestrator.Models.Planner;

namespace MealShopper.Orchestrator.Clients;

/// <summary>
/// Client interface for interacting with the Python Planning Domain service.
/// </summary>
public interface IPlanningClient
{
    /// <summary>
    /// Generates a meal plan draft based on regional deals, preferences, and dietary restrictions.
    /// </summary>
    /// <param name="request">Request parameters for generating the meal plan.</param>
    /// <param name="ct">Cancellation token.</param>
    /// <returns>The generated meal plan draft response.</returns>
    Task<MealPlanDraftResponse> GenerateMealPlanAsync(GenerateMealPlanRequest request, CancellationToken ct = default);
}
