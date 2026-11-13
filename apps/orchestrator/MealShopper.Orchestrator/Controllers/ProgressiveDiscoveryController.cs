using MealShopper.Common.Security;
using MealShopper.Orchestrator.Models;
using MealShopper.Orchestrator.Models.DTOs;
using MealShopper.Orchestrator.Models.Shopper;
using MealShopper.Orchestrator.Services;
using Microsoft.AspNetCore.Mvc;

namespace MealShopper.Orchestrator.Controllers;

/// <summary>Progressive deal retrieval for a completed store discovery.</summary>
[ApiController]
[Route("v1/meal-plans/discovery/{jobId:guid}")]
[RequireGatewayUser]
public sealed class ProgressiveDiscoveryController(
    IJobStateStore jobs,
    IProgressiveDiscoveryService discovery,
    IGatewayUserContext user,
    ILogger<ProgressiveDiscoveryController> logger) : ControllerBase
{
    /// <summary>Check cached deals without starting ingestion.</summary>
    [HttpGet("cache")]
    [ProducesResponseType(typeof(ProgressiveCacheResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> Cache(Guid jobId, CancellationToken ct)
    {
        var stores = await GetStoresAsync(jobId, ct);
        if (stores is null) return NotFound();
        try
        {
            return Ok(await discovery.GetCacheAsync(stores, ct));
        }
        catch (Exception ex) when (!ct.IsCancellationRequested)
        {
            logger.LogError(ex, "Cache lookup failed for discovery {JobId}", jobId);
            return Problem("Unable to check cached deals.", statusCode: StatusCodes.Status502BadGateway);
        }
    }

    /// <summary>Load deals for a store in the user's discovery.</summary>
    [HttpPost("stores/{storeId}/deals")]
    [ProducesResponseType(typeof(ProgressiveLoadResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> Load(Guid jobId, string storeId, CancellationToken ct)
    {
        var stores = await GetStoresAsync(jobId, ct);
        var store = stores?.Find(s => s.Id == storeId);
        if (store is null) return NotFound();
        try
        {
            return Ok(await discovery.LoadAsync(store, ct));
        }
        catch (Exception ex) when (!ct.IsCancellationRequested)
        {
            logger.LogError(ex, "Deal loading failed for store {StoreId} in discovery {JobId}", storeId, jobId);
            return Problem("Unable to load store deals.", statusCode: StatusCodes.Status502BadGateway);
        }
    }

    private async Task<List<Models.Domain.StoreDto>?> GetStoresAsync(Guid jobId, CancellationToken ct)
    {
        var job = await jobs.GetJobAsync(jobId, ct);
        if (job is null || job.UserId != user.UserId || job.JobType != JobType.StoreDiscovery ||
            job.Status != JobStatus.Completed || job.GetPayload<MealPlanDiscoveryRequest>()?.StoresOnly != true)
            return null;
        return job.GetResult<DiscoveryResultDto>()?.Stores;
    }
}
