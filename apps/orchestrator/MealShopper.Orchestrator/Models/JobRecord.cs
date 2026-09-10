using MealShopper.Orchestrator.Models.DTOs;

namespace MealShopper.Orchestrator.Models;

/// <summary>
/// Status states of a meal plan generation workflow job.
/// </summary>
public enum JobStatus
{
    Pending,
    DiscoveringStores,
    FetchingDeals,
    GeneratingMealPlan,
    Completed,
    Failed
}

/// <summary>
/// Represents the internal state and metadata for a meal planning job.
/// </summary>
public record JobRecord
{
    /// <summary>
    /// Unique identifier for the job.
    /// </summary>
    public Guid JobId { get; init; } = Guid.NewGuid();

    /// <summary>
    /// Current workflow execution status of the job.
    /// </summary>
    public JobStatus Status { get; init; } = JobStatus.Pending;

    /// <summary>
    /// Human-readable description of the current workflow stage.
    /// </summary>
    public string? StageDescription { get; init; }

    /// <summary>
    /// The intake request payload containing user preferences and constraints.
    /// </summary>
    public CreateMealPlanRequest RequestPayload { get; init; } = new();

    /// <summary>
    /// Timestamp when the job was created.
    /// </summary>
    public DateTimeOffset CreatedAt { get; init; } = DateTimeOffset.UtcNow;

    /// <summary>
    /// Timestamp when the job was last updated.
    /// </summary>
    public DateTimeOffset UpdatedAt { get; init; } = DateTimeOffset.UtcNow;

    /// <summary>
    /// Error message describing why the job failed, if applicable.
    /// </summary>
    public string? ErrorMessage { get; init; }
}
