using MealShopper.Orchestrator.Clients;
using MealShopper.Orchestrator.Models;
using MealShopper.Orchestrator.Models.Planner;
using Microsoft.Extensions.Logging;

namespace MealShopper.Orchestrator.Services;

/// <summary>
/// Orchestrates the asynchronous meal planning workflow across external domain services.
/// </summary>
public class MealPlanOrchestrator : IMealPlanOrchestrator
{
    private readonly IJobStateStore _jobStateStore;
    private readonly IShopperClient _shopperClient;
    private readonly IPlanningClient _planningClient;
    private readonly ILogger<MealPlanOrchestrator> _logger;

    public MealPlanOrchestrator(
        IJobStateStore jobStateStore,
        IShopperClient shopperClient,
        IPlanningClient planningClient,
        ILogger<MealPlanOrchestrator> logger)
    {
        _jobStateStore = jobStateStore ?? throw new ArgumentNullException(nameof(jobStateStore));
        _shopperClient = shopperClient ?? throw new ArgumentNullException(nameof(shopperClient));
        _planningClient = planningClient ?? throw new ArgumentNullException(nameof(planningClient));
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

            // 3. Generate Meal Plan
            await _jobStateStore.UpdateJobStatusAsync(
                jobId,
                JobStatus.GeneratingMealPlan,
                stageDescription: "Synthesizing customized recipes from curated deals...",
                cancellationToken: ct);

            var generateRequest = new GenerateMealPlanRequest
            {
                Cuisines = job.RequestPayload.Cuisines ?? [],
                AvoidIngredients = job.RequestPayload.AvoidIngredients ?? [],
                TopDeals = topDeals.Deals ?? []
            };

            var draft = await _planningClient.GenerateMealPlanAsync(generateRequest, ct);

            _logger.LogInformation(
                "Generated meal plan {MealPlanId} with {MealCount} meals and {MissingCount} missing primary ingredients for Job {JobId}.",
                draft.MealPlanId,
                draft.Meals.Count,
                draft.MissingPrimaryIngredients.Count,
                jobId);
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
