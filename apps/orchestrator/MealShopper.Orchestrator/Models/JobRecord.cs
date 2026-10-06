using System.Text.Json;

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
/// Types of meal planning jobs that can be executed in the orchestrator workflow.
/// </summary>
public enum JobType
{
    StoreDiscoveryAndPlanGeneration,
    StoreDiscovery,
    PlanGeneration
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

    public JobType JobType { get; init; } = JobType.StoreDiscoveryAndPlanGeneration;

    /// <summary>
    /// Current workflow execution status of the job.
    /// </summary>
    public JobStatus Status { get; init; } = JobStatus.Pending;

    /// <summary>
    /// Human-readable description of the current workflow stage.
    /// </summary>
    public string? StageDescription { get; init; }

    private CreateMealPlanRequest? _requestPayload;

    /// <summary>
    /// The intake request payload containing user preferences and constraints.
    /// </summary>
    public string RequestPayloadJson { get; init; } = string.Empty;

    /// <summary>
    /// Backward-compatible strongly-typed request payload.
    /// </summary>
    [System.Text.Json.Serialization.JsonIgnore]
    public CreateMealPlanRequest RequestPayload
    {
        get => _requestPayload ?? GetPayload<CreateMealPlanRequest>() ?? new();
        init
        {
            _requestPayload = value;
            if (value != null)
            {
                RequestPayloadJson = JsonSerializer.Serialize(value);
            }
        }
    }

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

    private MealPlanResultDto? _result;

    /// <summary>
    /// Serialized JSON string of the completed job result payload.
    /// </summary>
    public string? ResultPayloadJson { get; init; }

    /// <summary>
    /// Backward-compatible strongly-typed meal plan result when the job status is Completed.
    /// </summary>
    [System.Text.Json.Serialization.JsonIgnore]
    public MealPlanResultDto? Result
    {
        get
        {
            if (_result != null) return _result;
            if (JobType == JobType.StoreDiscovery) return null;
            return GetResult<MealPlanResultDto>();
        }
        init
        {
            _result = value;
            if (value != null)
            {
                ResultPayloadJson = JsonSerializer.Serialize(value);
            }
        }
    }

    public T? GetPayload<T>()
    {
        if (string.IsNullOrEmpty(RequestPayloadJson))
        {
            return default;
        }

        var options = new JsonSerializerOptions
        {
            PropertyNameCaseInsensitive = true
        };
        return JsonSerializer.Deserialize<T>(RequestPayloadJson, options);
    }

    public T? GetResult<T>()
    {
        if (string.IsNullOrEmpty(ResultPayloadJson))
        {
            return default;
        }

        var options = new JsonSerializerOptions
        {
            PropertyNameCaseInsensitive = true
        };
        return JsonSerializer.Deserialize<T>(ResultPayloadJson, options);
    }

    public object? GetResultObject()
    {
        if (string.IsNullOrEmpty(ResultPayloadJson))
        {
            return null;
        }

        var options = new JsonSerializerOptions
        {
            PropertyNameCaseInsensitive = true
        };
        return JsonSerializer.Deserialize<JsonElement>(ResultPayloadJson, options);
    }
}
