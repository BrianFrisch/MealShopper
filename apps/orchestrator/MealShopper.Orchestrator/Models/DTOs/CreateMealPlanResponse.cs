namespace MealShopper.Orchestrator.Models.DTOs;

/// <summary>
/// Represents the intake response payload returned when a meal plan generation job has been accepted.
/// </summary>
public record CreateMealPlanResponse
{
    /// <summary>
    /// Unique identifier for the asynchronous meal plan generation workflow instance.
    /// </summary>
    public Guid JobId { get; init; }

    /// <summary>
    /// Current execution status of the job (e.g., "Pending", "Processing", "Completed", "Failed").
    /// </summary>
    public string Status { get; init; } = "Pending";

    /// <summary>
    /// Timestamp indicating when the meal plan request was received and accepted.
    /// </summary>
    public DateTimeOffset CreatedAt { get; init; } = DateTimeOffset.UtcNow;
}
