using MealShopper.Orchestrator.Clients;
using MealShopper.Orchestrator.Models;
using Microsoft.Extensions.Logging;

namespace MealShopper.Orchestrator.Services;

/// <summary>
/// Orchestrates the asynchronous meal planning workflow across external domain services.
/// </summary>
public class MealPlanOrchestrator : IMealPlanOrchestrator
{
    private readonly IJobStateStore _jobStateStore;
    private readonly IShopperClient _shopperClient;
    private readonly ILogger<MealPlanOrchestrator> _logger;

    public MealPlanOrchestrator(
        IJobStateStore jobStateStore,
        IShopperClient shopperClient,
        ILogger<MealPlanOrchestrator> logger)
    {
        _jobStateStore = jobStateStore ?? throw new ArgumentNullException(nameof(jobStateStore));
        _shopperClient = shopperClient ?? throw new ArgumentNullException(nameof(shopperClient));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    /// <inheritdoc />
    public async Task ProcessJobAsync(Guid jobId, CancellationToken ct = default)
    {
        try
        {
            var job = await _jobStateStore.GetJobAsync(jobId, ct);
            if (job == null)
            {
                _logger.LogWarning("Job {JobId} was not found in state store for processing.", jobId);
                return;
            }

            _logger.LogInformation("Starting workflow processing for Job {JobId}.", jobId);

            // 1. Discover Stores
            await _jobStateStore.UpdateJobStatusAsync(
                jobId,
                JobStatus.DiscoveringStores,
                stageDescription: "Locating grocery stores within radius...",
                cancellationToken: ct);

            var address = job.RequestPayload.Address;
            var lat = address.Latitude ?? 34.053625;
            var lon = address.Longitude ?? -118.243007;
            var radiusMiles = job.RequestPayload.SearchRadiusMiles;
            var maxStores = job.RequestPayload.MaxStores;

            var stores = await _shopperClient.DiscoverStoresAsync(lat, lon, radiusMiles, maxStores, ct);
            _logger.LogInformation("Discovered {StoreCount} stores for Job {JobId}.", stores.Count, jobId);

            // 2. Fetch Deals
            await _jobStateStore.UpdateJobStatusAsync(
                jobId,
                JobStatus.FetchingDeals,
                stageDescription: "Fetching circulars and scoring top promotional deals...",
                cancellationToken: ct);

            var storeIds = stores.Select(s => s.StoreId).ToList();
            var avoidIngredients = job.RequestPayload.AvoidIngredients;

            var topDeals = await _shopperClient.GetTopDealsAsync(storeIds, avoidIngredients, ct);
            _logger.LogInformation("Retrieved {DealCount} deals for job {JobId}.", topDeals.Deals.Count, jobId);

            // 3. Placeholder for Story 2.4: Planning Domain handoff
            _logger.LogInformation("Job {JobId} is ready for Planning Domain handoff.", jobId);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Job {JobId} failed during orchestration execution.", jobId);
            await _jobStateStore.UpdateJobStatusAsync(
                jobId,
                JobStatus.Failed,
                errorMessage: ex.Message,
                stageDescription: "Workflow failed.",
                cancellationToken: ct);
        }
    }
}
