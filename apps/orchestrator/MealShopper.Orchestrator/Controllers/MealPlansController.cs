using Microsoft.AspNetCore.Mvc;
using System.Text.Json;

using MealShopper.Common.Security;
using MealShopper.Orchestrator.Models;
using MealShopper.Orchestrator.Models.DTOs;
using MealShopper.Orchestrator.Services;

namespace MealShopper.Orchestrator.Controllers;

[ApiController]
[Route("v1/meal-plans")]
public class MealPlansController : ControllerBase
{
    private readonly IJobStateStore _jobStateStore;
    private readonly IMealPlanOrchestrator _orchestrator;
    private readonly ILogger<MealPlansController> _logger;
    private readonly IGatewayUserContext _userContext;

    public MealPlansController(
        IJobStateStore jobStateStore,
        IMealPlanOrchestrator orchestrator,
        ILogger<MealPlansController> logger,
        IGatewayUserContext userContext)
    {
        _jobStateStore = jobStateStore ?? throw new ArgumentNullException(nameof(jobStateStore));
        _orchestrator = orchestrator ?? throw new ArgumentNullException(nameof(orchestrator));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _userContext = userContext ?? throw new ArgumentNullException(nameof(userContext));
    }



    /// <summary>
    /// Accepts a meal plan generation request and initiates the asynchronous planning workflow.
    /// </summary>
    /// <param name="request">User preferences, address, and search radius constraints.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>HTTP 202 Accepted with the job tracking details and Location header.</returns>
    [HttpPost]
    [ProducesResponseType(typeof(CreateMealPlanResponse), StatusCodes.Status202Accepted)]
    [ProducesResponseType(typeof(ValidationProblemDetails), StatusCodes.Status400BadRequest)]
    [RequireGatewayUser]
    public async Task<IActionResult> CreateMealPlan([FromBody] CreateMealPlanRequest request, CancellationToken cancellationToken)
    {
        if (!ModelState.IsValid)
        {
            return BadRequest(ModelState);
        }

        var jobId = Guid.NewGuid();
        var now = DateTimeOffset.UtcNow;

        var job = new JobRecord
        {
            JobId = jobId,
            UserId = _userContext.UserId,
            JobType = JobType.StoreDiscoveryAndPlanGeneration,
            Status = JobStatus.Pending,
            RequestPayloadJson = JsonSerializer.Serialize(request),
            CreatedAt = now,
            UpdatedAt = now
        };

        await _jobStateStore.CreateJobAsync(job, cancellationToken);

        _logger.LogInformation("Accepted meal plan generation request for {userId} ({roles}). JobId: {JobId}", _userContext.UserId, _userContext.Roles, job.JobId);

        // Trigger workflow execution asynchronously in background
        _ = Task.Run(async () =>
        {
            try
            {
                await _orchestrator.ProcessJobAsync(jobId);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Background orchestration processing failed for JobId: {JobId}", jobId);
            }
        });

        var locationUri = $"/v1/tasks/{job.JobId}";
        Response.Headers.Location = locationUri;

        var response = new CreateMealPlanResponse
        {
            JobId = job.JobId,
            Status = "Pending",
            CreatedAt = job.CreatedAt
        };

        return Accepted(locationUri, response);
    }

    /// <summary>
    /// Accepts a deal discovery request and initiates the asynchronous store and deal discovery workflow.
    /// </summary>
    /// <param name="request">User preferences, address, and search radius constraints.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>HTTP 202 Accepted with the job tracking details and Location header.</returns>
    [HttpPost("discovery")]
    [ProducesResponseType(typeof(CreateMealPlanResponse), StatusCodes.Status202Accepted)]
    [ProducesResponseType(typeof(ValidationProblemDetails), StatusCodes.Status400BadRequest)]
    [RequireGatewayUser]
    public async Task<IActionResult> DiscoverDeals([FromBody] MealPlanDiscoveryRequest request, CancellationToken cancellationToken)
    {
        if (!ModelState.IsValid)
        {
            return BadRequest(ModelState);
        }

        var jobId = Guid.NewGuid();
        var now = DateTimeOffset.UtcNow;

        var job = new JobRecord
        {
            JobId = jobId,
            JobType = JobType.StoreDiscovery,
            Status = JobStatus.Pending,
            RequestPayloadJson = JsonSerializer.Serialize(request),
            CreatedAt = now,
            UpdatedAt = now
        };

        await _jobStateStore.CreateJobAsync(job, cancellationToken);

        _logger.LogInformation("Accepted deal discovery request for {userId} ({roles}). JobId: {JobId}", _userContext.UserId, _userContext.Roles, job.JobId);

        // Trigger workflow execution asynchronously in background
        _ = Task.Run(async () =>
        {
            try
            {
                await _orchestrator.ProcessDiscoveryJobAsync(jobId);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Background discovery orchestration processing failed for JobId: {JobId}", jobId);
            }
        });

        var locationUri = $"/v1/tasks/{job.JobId}";
        Response.Headers.Location = locationUri;

        var response = new CreateMealPlanResponse
        {
            JobId = job.JobId,
            Status = "Pending",
            CreatedAt = job.CreatedAt
        };

        return Accepted(locationUri, response);
    }


        /// <summary>
    /// Accepts a meal plan generation request and initiates the asynchronous meal plan generation workflow.
    /// </summary>
    /// <param name="request">User preferences and deal information.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>HTTP 202 Accepted with the job tracking details and Location header.</returns>
    [HttpPost("generation")]
    [ProducesResponseType(typeof(CreateMealPlanResponse), StatusCodes.Status202Accepted)]
    [ProducesResponseType(typeof(ValidationProblemDetails), StatusCodes.Status400BadRequest)]
    [RequireGatewayUser]
    public async Task<IActionResult> GenerateMealPlanFromDeals([FromBody] MealPlanGenerationRequest request, CancellationToken cancellationToken)
    {
        if (!ModelState.IsValid)
        {
            return BadRequest(ModelState);
        }

        var jobId = Guid.NewGuid();
        var now = DateTimeOffset.UtcNow;

        var job = new JobRecord
        {
            JobId = jobId,
            UserId = _userContext.UserId,
            JobType = JobType.PlanGeneration,
            Status = JobStatus.Pending,
            RequestPayloadJson = JsonSerializer.Serialize(request),
            CreatedAt = now,
            UpdatedAt = now
        };

        await _jobStateStore.CreateJobAsync(job, cancellationToken);

        _logger.LogInformation("Accepted meal plan generation request for {userId} ({roles}). JobId: {JobId}", _userContext.UserId, _userContext.Roles, job.JobId);

        // Trigger workflow execution asynchronously in background
        _ = Task.Run(async () =>
        {
            try
            {
                await _orchestrator.ProcessGenerationJobAsync(jobId);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Background meal plan generation orchestration processing failed for JobId: {JobId}", jobId);
            }
        });

        var locationUri = $"/v1/tasks/{job.JobId}";
        Response.Headers.Location = locationUri;

        var response = new CreateMealPlanResponse
        {
            JobId = job.JobId,
            Status = "Pending",
            CreatedAt = job.CreatedAt
        };

        return Accepted(locationUri, response);
    }

    [HttpPost("{jobId:guid}/confirm")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(typeof(ValidationProblemDetails), StatusCodes.Status400BadRequest)]
    [RequireGatewayUser]
    public async Task<IActionResult> ConfirmMealPlan(
        [FromRoute] Guid jobId,
        [FromBody] ConfirmMealPlanRequest request,
        CancellationToken cancellationToken)
    {
        if (!ModelState.IsValid || request.SelectedRecipeIds.Count == 0)
        {
            return BadRequest(ModelState);
        }

        var job = await _jobStateStore.GetJobAsync(jobId, cancellationToken);
        if (job is null)
        {
            return NotFound(new { error = "meal_plan_not_found", message = $"Meal plan task {jobId} does not exist." });
        }

        if (job.JobType != JobType.PlanGeneration || job.Status != JobStatus.Completed)
        {
            return Conflict(new { error = "meal_plan_not_ready", message = "Only completed generated meal plans can be saved." });
        }

        var result = job.GetResult<MealPlanResultDto>();
        if (result is null)
        {
            return Conflict(new { error = "meal_plan_result_missing", message = "The completed meal plan has no result to save." });
        }

        var selectedRecipeIds = request.SelectedRecipeIds.ToHashSet(StringComparer.Ordinal);
        var existingRecipeIds = result.Recipes.Select(recipe => recipe.RecipeId).ToHashSet(StringComparer.Ordinal);
        if (selectedRecipeIds.Any(recipeId => !existingRecipeIds.Contains(recipeId)))
        {
            return BadRequest(new { error = "invalid_recipe_selection", message = "One or more selected recipes are not part of this meal plan." });
        }

        foreach (var recipe in result.Recipes)
        {
            recipe.IsKept = selectedRecipeIds.Contains(recipe.RecipeId);
        }

        var updatedJob = await _jobStateStore.CompleteJobAsync(
            jobId,
            result,
            stageDescription: "Meal plan saved successfully.",
            cancellationToken: cancellationToken);
        if (updatedJob is null)
        {
            return NotFound(new { error = "meal_plan_not_found", message = $"Meal plan task {jobId} does not exist." });
        }

        _logger.LogInformation(
            "Saved meal plan {MealPlanId} for task {JobId} with {KeptRecipeCount} kept recipes.",
            result.MealPlanId,
            jobId,
            selectedRecipeIds.Count);

        return Ok(new { taskId = jobId, mealPlanId = result.MealPlanId });
    }
}
