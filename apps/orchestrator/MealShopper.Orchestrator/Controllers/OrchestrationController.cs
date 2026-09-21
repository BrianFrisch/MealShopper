using MealShopper.Orchestrator.Services;
using Microsoft.AspNetCore.Mvc;

namespace MealShopper.Orchestrator.Controllers;

[ApiController]
[Route("v1/orchestrator/plans")]
public class OrchestrationController : ControllerBase
{
    private readonly IMealPlanOrchestrator _orchestrator;
    private readonly ILogger<OrchestrationController> _logger;

    public OrchestrationController(
        IMealPlanOrchestrator orchestrator,
        ILogger<OrchestrationController> logger)
    {
        _orchestrator = orchestrator ?? throw new ArgumentNullException(nameof(orchestrator));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    /// <summary>
    /// Executes the meal planning workflow and returns the consolidated meal plan result.
    /// </summary>
    /// <param name="request">The plan generation workflow request payload.</param>
    /// <param name="userId">The X-User-Id forwarded from the Gateway.</param>
    /// <param name="cancellationToken">Cancellation token.</param>
    /// <returns>The consolidated meal plan result.</returns>
    [HttpPost("generate")]
    [ProducesResponseType(typeof(ConsolidatedMealPlanResult), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status500InternalServerError)]
    public async Task<ActionResult<ConsolidatedMealPlanResult>> Generate(
        [FromBody] PlanGenerationWorkflowRequest request,
        [FromHeader(Name = "X-User-Id")] string? userId,
        CancellationToken cancellationToken)
    {
        _logger.LogInformation("Received plan generation request for User {UserId}.", userId ?? "Anonymous");

        var result = await _orchestrator.ExecuteWorkflowAsync(request, cancellationToken);
        return Ok(result);
    }
}
