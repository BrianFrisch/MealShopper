using Microsoft.AspNetCore.Mvc;
using MealShopper.Orchestrator.Services;
using MealShopper.Orchestrator.Models.DTOs;

namespace MealShopper.Orchestrator.Controllers;

[ApiController]
[Route("v1/tasks")]
public class TasksController : ControllerBase
{
    private readonly IJobStateStore _jobStore;
    private readonly ILogger<TasksController> _logger;

    public TasksController(IJobStateStore jobStore, ILogger<TasksController> logger)
    {
        _jobStore = jobStore;
        _logger = logger;
    }

    [HttpGet("{taskId:guid}")]
    public async Task<IActionResult> GetTaskStatus([FromRoute] Guid taskId, CancellationToken ct)
    {
        var job = await _jobStore.GetJobAsync(taskId, ct);
        if (job is null)
        {
            _logger.LogWarning("Polled task {TaskId} was not found.", taskId);
            return NotFound(new { error = "task_not_found", message = $"Task {taskId} does not exist." });
        }

        return Ok(new
        {
            jobId = job.JobId,
            status = job.Status.ToString(),
            stageDescription = job.StageDescription,
            createdAt = job.CreatedAt,
            updatedAt = job.UpdatedAt,
            result = job.Result,
            errorMessage = job.ErrorMessage
        });
    }
}