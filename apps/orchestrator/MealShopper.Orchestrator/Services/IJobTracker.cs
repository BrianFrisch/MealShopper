namespace MealShopper.Orchestrator.Services;

using MealShopper.Orchestrator.Models;

/// <summary>
/// Service interface for tracking and managing meal plan generation jobs.
/// </summary>
public interface IJobTracker
{
    /// <summary>
    /// Creates and persists a new job record.
    /// </summary>
    /// <param name="job">The job record to create.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>The created job record.</returns>
    Task<JobRecord> CreateJobAsync(JobRecord job, CancellationToken cancellationToken = default);

    /// <summary>
    /// Retrieves a job record by its identifier.
    /// </summary>
    /// <param name="jobId">The unique job ID.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>The job record if found; otherwise, null.</returns>
    Task<JobRecord?> GetJobAsync(Guid jobId, CancellationToken cancellationToken = default);

    /// <summary>
    /// Updates an existing job's status and optional error message and stage description.
    /// </summary>
    /// <param name="jobId">The unique job ID.</param>
    /// <param name="status">The new job status.</param>
    /// <param name="errorMessage">Optional error message if the status indicates a failure.</param>
    /// <param name="stageDescription">Optional human-readable description of the current stage.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>The updated job record if found; otherwise, null.</returns>
    Task<JobRecord?> UpdateJobStatusAsync(Guid jobId, JobStatus status, string? errorMessage = null, string? stageDescription = null, CancellationToken cancellationToken = default);
}
