using System.Collections.Concurrent;
using MealShopper.Orchestrator.Models;
using MealShopper.Orchestrator.Models.DTOs;

namespace MealShopper.Orchestrator.Services;

/// <summary>
/// Thread-safe in-memory implementation of <see cref="IJobTracker"/> and <see cref="IJobStateStore"/>.
/// </summary>
public class InMemoryJobTracker : IJobTracker, IJobStateStore
{
    private readonly ConcurrentDictionary<Guid, JobRecord> _jobs = new();

    /// <inheritdoc />
    public Task<JobRecord> CreateJobAsync(JobRecord job, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(job);

        _jobs[job.JobId] = job;
        return Task.FromResult(job);
    }

    /// <inheritdoc />
    public Task<JobRecord?> GetJobAsync(Guid jobId, CancellationToken cancellationToken = default)
    {
        _jobs.TryGetValue(jobId, out var job);
        return Task.FromResult(job);
    }

    /// <inheritdoc />
    public Task<JobRecord?> UpdateJobStatusAsync(
        Guid jobId,
        JobStatus status,
        string? errorMessage = null,
        string? stageDescription = null,
        CancellationToken cancellationToken = default)
    {
        if (_jobs.TryGetValue(jobId, out var job))
        {
            var updatedJob = job with
            {
                Status = status,
                StageDescription = stageDescription ?? job.StageDescription,
                UpdatedAt = DateTimeOffset.UtcNow,
                ErrorMessage = errorMessage
            };

            _jobs[jobId] = updatedJob;
            return Task.FromResult<JobRecord?>(updatedJob);
        }

        return Task.FromResult<JobRecord?>(null);
    }

    /// <inheritdoc />
    public Task<JobRecord?> CompleteJobAsync(
        Guid jobId,
        MealPlanResultDto result,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(result);

        if (_jobs.TryGetValue(jobId, out var job))
        {
            var updatedJob = job with
            {
                Status = JobStatus.Completed,
                StageDescription = "Meal plan generated successfully.",
                UpdatedAt = DateTimeOffset.UtcNow,
                Result = result,
                ErrorMessage = null
            };

            _jobs[jobId] = updatedJob;
            return Task.FromResult<JobRecord?>(updatedJob);
        }

        return Task.FromResult<JobRecord?>(null);
    }
}
