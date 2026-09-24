using System.Text.Json;
using System.Text.Json.Serialization;
using MealShopper.Orchestrator.Exceptions;
using MealShopper.Orchestrator.Models;
using MealShopper.Orchestrator.Models.DTOs;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;
using StackExchange.Redis;

namespace MealShopper.Orchestrator.Services;

/// <summary>
/// Redis-backed implementation of <see cref="IJobStateStore"/> and <see cref="IJobTracker"/>.
/// </summary>
public class RedisJobStateStore : IJobStateStore, IJobTracker
{
    private static readonly TimeSpan DefaultExpiry = TimeSpan.FromHours(24);

    private static readonly JsonSerializerOptions SerializerOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        PropertyNameCaseInsensitive = true,
        Converters = { new JsonStringEnumConverter(JsonNamingPolicy.CamelCase) }
    };

    private readonly IConnectionMultiplexer _redis;
    private readonly IDatabase _db;
    private readonly ILogger<RedisJobStateStore> _logger;
    private readonly string _instanceName;

    public RedisJobStateStore(
        IConnectionMultiplexer redis,
        IConfiguration config,
        ILogger<RedisJobStateStore> logger)
    {
        _redis = redis ?? throw new ArgumentNullException(nameof(redis));
        ArgumentNullException.ThrowIfNull(config);
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));

        _db = _redis.GetDatabase();
        _instanceName = config["Redis:InstanceName"] ?? "mealshopper:jobs:";
    }

    /// <inheritdoc />
    public async Task<JobRecord> CreateJobAsync(JobRecord job, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(job);

        try
        {
            var key = GetKey(job.JobId);
            var json = JsonSerializer.Serialize(job, SerializerOptions);
            await _db.StringSetAsync(key, json, DefaultExpiry);

            _logger.LogInformation("Job {JobId} created in Redis state store with status {Status}.", job.JobId, job.Status);
            return job;
        }
        catch (Exception ex) when (ex is RedisException or TimeoutException)
        {
            _logger.LogError(ex, "Redis error occurred while creating job {JobId}.", job.JobId);
            throw new DomainException($"Failed to create job {job.JobId} in Redis state store.", ex);
        }
        catch (Exception ex) when (ex is not DomainException)
        {
            _logger.LogError(ex, "Unexpected error occurred while creating job {JobId}.", job.JobId);
            throw;
        }
    }

    /// <summary>
    /// Creates and persists a new job record from a create meal plan request payload with status Pending and 24-hour expiry.
    /// </summary>
    /// <param name="payload">The intake request payload.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>The created job record.</returns>
    public Task<JobRecord> CreateJobAsync(CreateMealPlanRequest payload, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(payload);

        var now = DateTimeOffset.UtcNow;
        var job = new JobRecord
        {
            JobId = Guid.NewGuid(),
            Status = JobStatus.Pending,
            RequestPayload = payload,
            CreatedAt = now,
            UpdatedAt = now
        };

        return CreateJobAsync(job, cancellationToken);
    }

    /// <inheritdoc />
    public async Task<JobRecord?> GetJobAsync(Guid jobId, CancellationToken cancellationToken = default)
    {
        try
        {
            var key = GetKey(jobId);
            var value = await _db.StringGetAsync(key);
            if (!value.HasValue || value.IsNullOrEmpty)
            {
                return null;
            }

            return JsonSerializer.Deserialize<JobRecord>(value.ToString(), SerializerOptions);
        }
        catch (Exception ex) when (ex is RedisException or TimeoutException)
        {
            _logger.LogError(ex, "Redis error occurred while retrieving job {JobId}.", jobId);
            throw new DomainException($"Failed to retrieve job {jobId} from Redis state store.", ex);
        }
        catch (Exception ex) when (ex is not DomainException)
        {
            _logger.LogError(ex, "Unexpected error occurred while retrieving job {JobId}.", jobId);
            throw;
        }
    }

    /// <inheritdoc />
    public async Task<JobRecord?> UpdateJobStatusAsync(
        Guid jobId,
        JobStatus status,
        string? errorMessage = null,
        string? stageDescription = null,
        CancellationToken cancellationToken = default)
    {
        try
        {
            var key = GetKey(jobId);
            var value = await _db.StringGetAsync(key);
            if (!value.HasValue || value.IsNullOrEmpty)
            {
                _logger.LogWarning("Attempted to update status for job {JobId}, but it was not found.", jobId);
                return null;
            }

            var existingJob = JsonSerializer.Deserialize<JobRecord>(value.ToString(), SerializerOptions);
            if (existingJob is null)
            {
                _logger.LogWarning("Failed to deserialize existing job record for job {JobId}.", jobId);
                return null;
            }

            var updatedJob = existingJob with
            {
                Status = status,
                StageDescription = stageDescription ?? existingJob.StageDescription,
                UpdatedAt = DateTimeOffset.UtcNow,
                ErrorMessage = errorMessage
            };

            var json = JsonSerializer.Serialize(updatedJob, SerializerOptions);
            await _db.StringSetAsync(key, json, DefaultExpiry);

            _logger.LogInformation("Updated job {JobId} status to {Status} in Redis state store.", jobId, status);
            return updatedJob;
        }
        catch (Exception ex) when (ex is RedisException or TimeoutException)
        {
            _logger.LogError(ex, "Redis error occurred while updating status for job {JobId}.", jobId);
            throw new DomainException($"Failed to update status for job {jobId} in Redis state store.", ex);
        }
        catch (Exception ex) when (ex is not DomainException)
        {
            _logger.LogError(ex, "Unexpected error occurred while updating status for job {JobId}.", jobId);
            throw;
        }
    }

    /// <inheritdoc />
    public async Task<JobRecord?> CompleteJobAsync(
        Guid jobId,
        MealPlanResultDto result,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(result);

        try
        {
            var key = GetKey(jobId);
            var value = await _db.StringGetAsync(key);
            if (!value.HasValue || value.IsNullOrEmpty)
            {
                _logger.LogWarning("Attempted to complete job {JobId}, but it was not found.", jobId);
                return null;
            }

            var existingJob = JsonSerializer.Deserialize<JobRecord>(value.ToString(), SerializerOptions);
            if (existingJob is null)
            {
                _logger.LogWarning("Failed to deserialize existing job record for job {JobId}.", jobId);
                return null;
            }

            var updatedJob = existingJob with
            {
                Status = JobStatus.Completed,
                StageDescription = "Meal plan generated successfully.",
                UpdatedAt = DateTimeOffset.UtcNow,
                Result = result,
                ErrorMessage = null
            };

            var json = JsonSerializer.Serialize(updatedJob, SerializerOptions);
            await _db.StringSetAsync(key, json, DefaultExpiry);

            _logger.LogInformation("Job {JobId} marked as Completed in Redis state store.", jobId);
            return updatedJob;
        }
        catch (Exception ex) when (ex is RedisException or TimeoutException)
        {
            _logger.LogError(ex, "Redis error occurred while completing job {JobId}.", jobId);
            throw new DomainException($"Failed to complete job {jobId} in Redis state store.", ex);
        }
        catch (Exception ex) when (ex is not DomainException)
        {
            _logger.LogError(ex, "Unexpected error occurred while completing job {JobId}.", jobId);
            throw;
        }
    }

    private string GetKey(Guid jobId) => $"{_instanceName}{jobId}";
}
