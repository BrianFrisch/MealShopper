using MealShopper.Orchestrator.Models;
using MealShopper.Orchestrator.Models.DTOs;

namespace MealShopper.Orchestrator.Services;

/// <summary>
/// Service interface for persisting and managing meal plan job states.
/// </summary>
public interface IJobStateStore
{
    /// <summary>
    /// Persists a new job record.
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

    /// <summary>
    /// Transitions an existing job to the Completed status with the final result.
    /// </summary>
    /// <typeparam name="T">The type of the result payload.</typeparam>
    /// <param name="jobId">The unique job ID.</param>
    /// <param name="result">The result payload object or raw JSON string.</param>
    /// <param name="stageDescription">Optional stage description upon completion.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>The updated job record if found; otherwise, null.</returns>
    Task<JobRecord?> CompleteJobAsync<T>(Guid jobId, T result, string? stageDescription = "Completed successfully.", CancellationToken cancellationToken = default);
}
