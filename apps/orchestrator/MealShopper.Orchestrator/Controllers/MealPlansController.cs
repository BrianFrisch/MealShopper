using Microsoft.AspNetCore.Mvc;
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

    public MealPlansController(
        IJobStateStore jobStateStore,
        IMealPlanOrchestrator orchestrator,
        ILogger<MealPlansController> logger)
    {
        _jobStateStore = jobStateStore ?? throw new ArgumentNullException(nameof(jobStateStore));
        _orchestrator = orchestrator ?? throw new ArgumentNullException(nameof(orchestrator));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
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
            Status = JobStatus.Pending,
            RequestPayload = request,
            CreatedAt = now,
            UpdatedAt = now
        };

        await _jobStateStore.CreateJobAsync(job, cancellationToken);

        _logger.LogInformation("Accepted meal plan generation request. JobId: {JobId}", job.JobId);

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
}
