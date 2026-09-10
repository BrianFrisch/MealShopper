namespace MealShopper.Orchestrator.Services;

/// <summary>
/// Service interface for coordinating the end-to-end meal plan generation workflow pipeline.
/// </summary>
public interface IMealPlanOrchestrator
{
    /// <summary>
    /// Processes a meal planning job through store discovery, deal evaluation, and menu generation.
    /// </summary>
    /// <param name="jobId">The unique job identifier.</param>
    /// <param name="ct">Cancellation token.</param>
    Task ProcessJobAsync(Guid jobId, CancellationToken ct = default);
}
