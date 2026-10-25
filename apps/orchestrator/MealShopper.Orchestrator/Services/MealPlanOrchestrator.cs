using MealShopper.Orchestrator.Clients;
using MealShopper.Orchestrator.Exceptions;
using MealShopper.Orchestrator.Models;
using MealShopper.Orchestrator.Models.Domain;
using MealShopper.Orchestrator.Models.DTOs;
using MealShopper.Orchestrator.Models.Planner;
using MealShopper.Orchestrator.Models.Shopper;
using Microsoft.Extensions.Logging;

namespace MealShopper.Orchestrator.Services;

/// <summary>
/// Orchestrates the meal planning workflow across external domain services.
/// </summary>
public class MealPlanOrchestrator : IMealPlanOrchestrator
{
    private readonly IShopperClient _shopperClient;
    private readonly IPlannerClient _plannerClient;
    private readonly ILogger<MealPlanOrchestrator> _logger;
    private readonly IJobStateStore? _jobStateStore;
    private readonly IPlanningClient? _legacyPlanningClient;
    private readonly IGeocodingService _geocodingService;

    public MealPlanOrchestrator(
        IShopperClient shopperClient,
        IPlannerClient plannerClient,
        IPlanningClient planningClient,
        IJobStateStore jobStateStore,
        ILogger<MealPlanOrchestrator> logger,
        IGeocodingService geocodingService)
    {
        _shopperClient = shopperClient ?? throw new ArgumentNullException(nameof(shopperClient));
        _plannerClient = plannerClient ?? throw new ArgumentNullException(nameof(plannerClient));
        _legacyPlanningClient = planningClient ?? throw new ArgumentNullException(nameof(planningClient));
        _jobStateStore = jobStateStore ?? throw new ArgumentNullException(nameof(jobStateStore));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _geocodingService = geocodingService ?? throw new ArgumentNullException(nameof(geocodingService));
    }


    /// <inheritdoc />
    public async Task<ConsolidatedMealPlanResult> ExecuteWorkflowAsync(
        PlanGenerationWorkflowRequest request,
        CancellationToken ct = default)
    {
        ArgumentNullException.ThrowIfNull(request);

        _logger.LogInformation(
            "Executing meal plan workflow for coordinates ({Latitude}, {Longitude}) with radius {RadiusMiles} miles.",
            request.Latitude, request.Longitude, request.RadiusMiles);

        // Step 1: Discover stores
        var stores = await DiscoverStoresWorkflowStepAsync(request, ct);
        var storeIds = stores.Select(s => s.Id).ToList();

        // Step 2: Score deals
        var scoredDeals = await ScoreDealsWorkflowStepAsync(storeIds, request.AvoidIngredients, ct);

        // Step 3: Generate meal plan
        var planRes = await GeneratePlanWorkflowStepAsync(request, scoredDeals, ct);

        // Step 4 (Loop-back): Match missing primary ingredients
        var matchedSecondaryDeals = await MatchSecondaryDealsWorkflowStepAsync(
            storeIds,
            planRes?.MissingPrimaryIngredients,
            ct);

        // Step 5: Consolidate and return
        return ConsolidateWorkflowResult(planRes, stores, matchedSecondaryDeals);
    }

    private async Task<List<StoreDto>> DiscoverStoresWorkflowStepAsync(
        PlanGenerationWorkflowRequest request,
        CancellationToken ct)
    {
        var discoveryReq = new StoreDiscoveryRequest
        {
            Latitude = request.Latitude,
            Longitude = request.Longitude,
            RadiusMiles = request.RadiusMiles
        };

        var discoveryRes = await _shopperClient.DiscoverStoresAsync(discoveryReq, ct);
        if (discoveryRes?.Stores == null || discoveryRes.Stores.Count == 0)
        {
            _logger.LogWarning("No stores found within radius of {RadiusMiles} miles.", request.RadiusMiles);
            throw new DomainException("No stores within radius");
        }

        _logger.LogInformation("Step 1 complete: Discovered {StoreCount} stores.", discoveryRes.Stores.Count);
        return discoveryRes.Stores;
    }

    private async Task<List<DealDto>> ScoreDealsWorkflowStepAsync(
        List<string> storeIds,
        List<string>? avoidIngredients,
        CancellationToken ct)
    {
        var scoringReq = new DealScoringRequest
        {
            StoreIds = storeIds,
            AvoidIngredients = avoidIngredients ?? new List<string>(),
            TopN = 10
        };

        var scoringRes = await _shopperClient.ScoreDealsAsync(scoringReq, ct);
        var scoredDeals = scoringRes?.Deals ?? new List<DealDto>();

        _logger.LogInformation("Step 2 complete: Retrieved {DealCount} scored deals.", scoredDeals.Count);
        return scoredDeals;
    }

    private async Task<MealPlanResponseDto?> GeneratePlanWorkflowStepAsync(
        PlanGenerationWorkflowRequest request,
        List<DealDto> scoredDeals,
        CancellationToken ct)
    {
        var planReq = new MealPlanRequestDto
        {
            ScoredDeals = scoredDeals,
            HouseholdSize = request.HouseholdSize,
            TargetMealCount = request.TargetMealCount,
            PreferredCuisines = request.PreferredCuisines ?? new List<string>(),
            DietaryRestrictions = request.DietaryRestrictions ?? new List<string>(),
            AvoidIngredients = request.AvoidIngredients ?? new List<string>()
        };

        var planRes = await _plannerClient.GeneratePlanAsync(planReq, ct);

        _logger.LogInformation(
            "Step 3 complete: Generated plan {PlanId} with {MealCount} meals and {MissingCount} missing primary ingredients.",
            planRes?.PlanId, planRes?.Meals?.Count ?? 0, planRes?.MissingPrimaryIngredients?.Count ?? 0);

        return planRes;
    }

    private async Task<List<MatchedDealDto>> MatchSecondaryDealsWorkflowStepAsync(
        List<string> storeIds,
        List<string>? missingIngredients,
        CancellationToken ct)
    {
        if (missingIngredients is not { Count: > 0 })
        {
            return [];
        }

        _logger.LogInformation(
            "Step 4 (Loop-back): Matching {MissingCount} missing primary ingredients across stores.",
            missingIngredients.Count);

        var matchReq = new IngredientMatchRequestDto
        {
            StoreIds = storeIds,
            MissingIngredients = missingIngredients,
            SimilarityThreshold = 65.0
        };

        var matchRes = await _shopperClient.MatchIngredientsAsync(matchReq, ct);
        var matchedSecondaryDeals = matchRes?.Matches ?? [];

        _logger.LogInformation("Step 4 complete: Matched {MatchCount} secondary deals.", matchedSecondaryDeals.Count);
        return matchedSecondaryDeals;
    }

    private ConsolidatedMealPlanResult ConsolidateWorkflowResult(
        MealPlanResponseDto? planRes,
        List<StoreDto> stores,
        List<MatchedDealDto> matchedSecondaryDeals)
    {
        var result = new ConsolidatedMealPlanResult(
            PlanId: planRes?.PlanId ?? string.Empty,
            SelectedStores: stores,
            Meals: planRes?.Meals ?? new List<PlannedMealDto>(),
            MatchedSecondaryDeals: matchedSecondaryDeals,
            EstimatedTotalSpend: planRes?.EstimatedTotalSpend ?? 0m,
            GeneratedAt: DateTimeOffset.UtcNow
        );

        _logger.LogInformation(
            "Step 5 complete: Consolidated meal plan result {PlanId} created successfully.",
            result.PlanId);

        return result;
    }

    private sealed record DealPriceInfo(decimal Price, string Unit);
    private sealed record DealFetchStageResult(
        TopDealsResponse Deals,
        int SuccessfulStoreCount,
        IReadOnlyList<string> FailedStoreIds);

    /// <inheritdoc />
    public async Task ProcessJobAsync(Guid jobId, CancellationToken ct = default)
    {
        if (_jobStateStore == null)
        {
            throw new InvalidOperationException("Job state store is not configured for this orchestrator instance.");
        }

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
            var stores = await DiscoverStoresStageAsync(job, ct);

            // 2. Fetch Deals
            var candidateStores = stores.Count > 0
                ? stores
                : new List<StoreDto>
                {
                    new() { Id = "ralphs-90260", Name = "Ralphs", ZipCode = "90260" },
                    new() { Id = "aldi-90260", Name = "ALDI", ZipCode = "90260" }
                };

            var dealFetchResult = await FetchDealsStageAsync(job.JobId, candidateStores, ct);
            var topDeals = dealFetchResult.Deals;

            // 3. Generate Meal Plan
            if (_legacyPlanningClient == null)
            {
                return;
            }

            var payload = job.GetPayload<CreateMealPlanRequest>()!;
            var draft = await GenerateMealPlanStageAsync(
                job.JobId, payload.Cuisines, payload.AvoidIngredients, topDeals, job.UserId, ct);

            // 4. Phase 6 Loop-Back: Resolve missing primary ingredients
            var candidateStoreIds = candidateStores.Select(s => s.Id).ToList();
            var matchedDeals = await ResolveMissingIngredientsStageAsync(job.JobId, draft, candidateStoreIds, ct);

            // 5. Assemble Final Result (MealPlanResultDto)
            var finalResultDto = AssembleFinalResult(draft, topDeals, matchedDeals);

            // 6. Transition Job to Completed
            await _jobStateStore.CompleteJobAsync(
                jobId,
                finalResultDto,
                stageDescription: GetDealFetchCompletionDescription(
                    "Meal plan generated successfully.",
                    dealFetchResult,
                    candidateStores.Count),
                cancellationToken: ct);

            _logger.LogInformation(
                "Completed meal plan generation for Job {JobId}. Total Cost: {TotalCost:C}, Recipes Count: {RecipeCount}, Required Stores: {StoreCount}.",
                jobId,
                finalResultDto.EstimatedTotalTripCost,
                finalResultDto.Recipes.Count,
                finalResultDto.RequiredStores.Count);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Job {JobId} failed during orchestration execution.", jobId);
            await _jobStateStore.UpdateJobStatusAsync(
                jobId,
                JobStatus.Failed,
                errorMessage: ex.Message,
                stageDescription: "Workflow failed.",
                cancellationToken: CancellationToken.None);
        }
    }

    /// <inheritdoc />
    public async Task ProcessDiscoveryJobAsync(Guid jobId, CancellationToken ct = default)
    {
        if (_jobStateStore == null)
        {
            throw new InvalidOperationException("Job state store is not configured for this orchestrator instance.");
        }

        try
        {
            var job = await _jobStateStore.GetJobAsync(jobId, ct);
            if (job == null)
            {
                _logger.LogWarning("Job {JobId} was not found in state store for processing.", jobId);
                return;
            }

            _logger.LogInformation("Starting deal discovery workflow processing for Job {JobId}.", jobId);

            // 1. Discover Stores
            var stores = await DiscoverStoresStageAsync(job, ct);

            if (stores.Count == 0)
            {
                _logger.LogInformation("No stores found within search radius for Job {JobId}. Completing discovery workflow gracefully.", jobId);
                await _jobStateStore.CompleteJobAsync(
                    jobId,
                    new DiscoveryResultDto { Stores = [], Deals = [] },
                    stageDescription: "No stores found within search radius.",
                    cancellationToken: ct);
                return;
            }

            // 2. Fetch Deals
            var dealFetchResult = await FetchDealsStageAsync(job.JobId, stores, ct);
            var topDeals = dealFetchResult.Deals;

            // 3. Assemble Discovery Result
            var discoveryResult = new DiscoveryResultDto
            {
                Stores = stores,
                Deals = topDeals.Deals
            };

            // 4. Transition Job to Completed with Discovery Result
            await _jobStateStore.CompleteJobAsync(
                jobId,
                discoveryResult,
                stageDescription: GetDealFetchCompletionDescription(
                    "Deals discovered successfully.",
                    dealFetchResult,
                    stores.Count),
                cancellationToken: ct);

            _logger.LogInformation(
                "Completed deal discovery for Job {JobId}. Deals Count: {DealCount}, Stores Count: {StoreCount}.",
                jobId,
                topDeals.Deals.Count,
                stores.Count);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Job {JobId} failed during deal discovery orchestration execution.", jobId);
            await _jobStateStore.UpdateJobStatusAsync(
                jobId,
                JobStatus.Failed,
                errorMessage: ex.Message,
                stageDescription: "Deal discovery workflow failed.",
                cancellationToken: CancellationToken.None);
        }
    }

    public async Task ProcessGenerationJobAsync(Guid jobId, CancellationToken ct = default)
    {
        if (_jobStateStore == null)
        {
            throw new InvalidOperationException("Job state store is not configured for this orchestrator instance.");
        }

        try
        {
            var job = await _jobStateStore.GetJobAsync(jobId, ct);
            if (job == null)
            {
                _logger.LogWarning("Job {JobId} was not found in state store for processing.", jobId);
                return;
            }

            _logger.LogInformation("Starting workflow processing for Job {JobId}.", jobId);

            // 3. Generate Meal Plan
            if (_legacyPlanningClient == null)
            {
                return;
            }

            var payload = job.GetPayload<MealPlanGenerationRequest>()!;
            var selectedDealLookups = BuildSelectedDealLookups(payload);
            var batchLookupResponse = await _shopperClient.BatchLookupDealsAsync(selectedDealLookups, ct);
            if (batchLookupResponse.Deals.Count != selectedDealLookups.Items.Count)
            {
                throw new InvalidOperationException(
                    $"Only {batchLookupResponse.Deals.Count} of {selectedDealLookups.Items.Count} selected deals could be found. " +
                    "Return to Discover and select current deals again.");
            }

            var topDeals = new TopDealsResponse
            {
                Timestamp = DateTimeOffset.UtcNow,
                RegionContext = new RegionContextDto { StoreIds = payload.SelectedStoreIds.Distinct().ToList() },
                Deals = batchLookupResponse.Deals.Select(deal => new DealItemDto
                {
                    DealId = deal.DealId,
                    StoreId = deal.StoreId,
                    StoreName = deal.StoreName,
                    ItemName = deal.ItemName,
                    CleanName = deal.ItemName,
                    NormalizedCategory = deal.Category,
                    PrimaryIngredient = deal.PrimaryIngredient,
                    DealPrice = deal.Price,
                    Unit = deal.Unit,
                    ValueScore = deal.DealScore ?? 0
                }).ToList()
            };

            var draft = await GenerateMealPlanStageAsync(
                job.JobId,
                payload.Cuisines,
                payload.AvoidIngredients,
                topDeals,
                job.UserId,
                ct,
                payload.DietaryPreferences,
                payload.DaysCount,
                payload.ServingsCount);

            ApplySelectedDealMatches(draft.Meals, topDeals.Deals);

            // 4. Phase 6 Loop-Back: Resolve missing primary ingredients
            var candidateStoreIds = payload.SelectedStoreIds;
            var matchedDeals = await ResolveMissingIngredientsStageAsync(job.JobId, draft, candidateStoreIds, ct);

            // 5. Assemble Final Result (MealPlanResultDto)
            var finalResultDto = AssembleFinalResult(draft, topDeals, matchedDeals);

            // 6. Transition Job to Completed
            await _jobStateStore.CompleteJobAsync(
                jobId,
                finalResultDto,
                stageDescription: "Meal plan generated successfully.",
                cancellationToken: ct);

            _logger.LogInformation(
                "Completed meal plan generation for Job {JobId}. Total Cost: {TotalCost:C}, Recipes Count: {RecipeCount}, Required Stores: {StoreCount}.",
                jobId,
                finalResultDto.EstimatedTotalTripCost,
                finalResultDto.Recipes.Count,
                finalResultDto.RequiredStores.Count);
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

    private static DealBatchLookupRequest BuildSelectedDealLookups(MealPlanGenerationRequest payload)
    {
        var storeIds = payload.SelectedStoreIds
            .Where(storeId => !string.IsNullOrWhiteSpace(storeId))
            .Distinct(StringComparer.Ordinal)
            .ToList();
        var dealIds = payload.SelectedDealIds
            .Where(dealId => !string.IsNullOrWhiteSpace(dealId))
            .Distinct(StringComparer.Ordinal)
            .ToList();

        var lookups = dealIds.Select(dealId =>
        {
            var selectedStoreId = storeIds
                .Where(candidate => dealId.StartsWith($"{candidate}_", StringComparison.Ordinal))
                .OrderByDescending(candidate => candidate.Length)
                .FirstOrDefault();

            var sourceDealId = selectedStoreId is null
                ? dealId
                : dealId[(selectedStoreId.Length + 1)..];
            var sourceStoreSeparator = sourceDealId.IndexOf('_');
            var candidateSourceStoreId = sourceStoreSeparator > 0
                ? sourceDealId[..sourceStoreSeparator]
                : null;
            var hasEmbeddedSourceStoreId = candidateSourceStoreId is not null &&
                IsStoreIdentifier(candidateSourceStoreId, storeIds);

            if (selectedStoreId is null && !hasEmbeddedSourceStoreId)
            {
                throw new InvalidOperationException(
                    $"Selected deal '{dealId}' is not prefixed by a selected store and does not contain a source store ID. Return to Discover and select the deal again.");
            }

            var sourceStoreId = hasEmbeddedSourceStoreId
                ? candidateSourceStoreId!
                : selectedStoreId ?? throw new InvalidOperationException(
                    $"Selected deal '{dealId}' does not contain a source store ID.");

            return new DealLookupItemDto
            {
                DealId = sourceDealId,
                StoreId = sourceStoreId
            };
        }).ToList();

        if (lookups.Count == 0)
        {
            throw new InvalidOperationException("At least one valid selected deal is required to generate a meal plan.");
        }

        return new DealBatchLookupRequest { Items = lookups };
    }

    private static bool IsStoreIdentifier(string candidate, IReadOnlyCollection<string> selectedStoreIds)
    {
        if (selectedStoreIds.Contains(candidate, StringComparer.Ordinal))
        {
            return true;
        }

        var separatorIndex = candidate.LastIndexOf('-');
        if (separatorIndex <= 0 || separatorIndex == candidate.Length - 1)
        {
            return false;
        }

        var chainPart = candidate[..separatorIndex];
        var storeNumberPart = candidate[(separatorIndex + 1)..];
        return chainPart.Any(char.IsLetter) && storeNumberPart.All(char.IsLetterOrDigit);
    }

    private static void ApplySelectedDealMatches(
        List<PlannedMealDto> meals,
        List<DealItemDto> selectedDeals)
    {
        var dealsById = selectedDeals.ToDictionary(deal => deal.DealId, StringComparer.OrdinalIgnoreCase);
        var dealsByIngredient = selectedDeals
            .SelectMany(deal => new[] { deal.ItemName, deal.CleanName, deal.PrimaryIngredient }
                .Where(name => !string.IsNullOrWhiteSpace(name))
                .Select(name => (Name: NormalizeIngredientName(name), Deal: deal)))
            .Where(match => match.Name.Length > 0)
            .GroupBy(match => match.Name, StringComparer.OrdinalIgnoreCase)
            .ToDictionary(group => group.Key, group => group.First().Deal, StringComparer.OrdinalIgnoreCase);

        foreach (var ingredient in meals.SelectMany(meal => meal.Ingredients))
        {
            DealItemDto? selectedDeal = null;
            if (!string.IsNullOrWhiteSpace(ingredient.DealId))
            {
                dealsById.TryGetValue(ingredient.DealId, out selectedDeal);
            }

            if (selectedDeal is null)
            {
                dealsByIngredient.TryGetValue(NormalizeIngredientName(ingredient.Name), out selectedDeal);
            }

            if (selectedDeal is null)
            {
                continue;
            }

            ingredient.DealId = selectedDeal.DealId;
            ingredient.StoreName = selectedDeal.StoreName;
            ingredient.IsPromotional = true;
        }
    }

    private static string NormalizeIngredientName(string value)
    {
        var tokens = System.Text.RegularExpressions.Regex
            .Matches(value.ToLowerInvariant(), "[a-z0-9]+")
            .Select(match => match.Value)
            .Select(token => token.Length > 4 && token.EndsWith('s') ? token[..^1] : token);
        return string.Join(' ', tokens);
    }

    private async Task<List<StoreDto>> DiscoverStoresStageAsync(JobRecord job, CancellationToken ct)
    {
        await _jobStateStore!.UpdateJobStatusAsync(
            job.JobId,
            JobStatus.DiscoveringStores,
            stageDescription: "Locating grocery stores within radius...",
            cancellationToken: ct);
        
        var payload = job.GetPayload<MealPlanDiscoveryRequest>()!;
        var address = payload.Address;
        var lat = address.Latitude ?? 33.894893;
        var lon = address.Longitude ?? -118.362658;

        if(address.Latitude.HasValue && address.Longitude.HasValue)
        {
            _logger.LogInformation(
                "Using provided coordinates ({Latitude}, {Longitude}) for store discovery.",
                address.Latitude.Value, address.Longitude.Value);
            lat = address.Latitude.Value;
            lon = address.Longitude.Value;
        }
        else
        {
            _logger.LogInformation(
                "No coordinates provided. Resolving coordinates for address: {Street}, {City}, {State} {ZipCode}.",
                address.Street, address.City, address.State, address.ZipCode);

            (lat, lon) = await _geocodingService.ResolveCoordinatesAsync(address, ct);

            _logger.LogInformation(
                "Resolved coordinates: ({Latitude}, {Longitude}) for store discovery.",
                lat, lon);
        }


        var radiusMiles = payload.SearchRadiusMiles;

        var stores = await _shopperClient.DiscoverStoresAsync(lat, lon, radiusMiles, ct);
        if (!string.IsNullOrWhiteSpace(address.ZipCode))
        {
            foreach (var store in stores)
            {
                if (string.IsNullOrWhiteSpace(store.PostalCode))
                {
                    _logger.LogWarning("Store {StoreId} ({StoreName}) is missing postal code. Assigning from request address: {PostalCode}.", store.Id, store.Name, address.ZipCode);
                    // store.PostalCode = address.ZipCode;
                }
            }
        }

        _logger.LogInformation("Discovered {StoreCount} stores for Job {JobId}.", stores.Count, job.JobId);
        foreach(StoreDto store in stores)
        {
            _logger.LogInformation("Store: {StoreId} - {StoreName} ({PostalCode})", store.Id, store.Name, store.PostalCode);
        }
        return stores;
    }

    private async Task<DealFetchStageResult> FetchDealsStageAsync(
        Guid jobId,
        List<StoreDto> stores,
        CancellationToken ct)
    {
        var totalStoreCount = stores.Count;
        await _jobStateStore!.UpdateJobStatusAsync(
            jobId,
            JobStatus.FetchingDeals,
            stageDescription: $"Fetching deals from stores (0/{totalStoreCount})",
            cancellationToken: ct);

        using var progressLock = new SemaphoreSlim(1, 1);
        using var concurrencyLimiter = new SemaphoreSlim(4, 4);
        var successfulStoreCount = 0;
        var dealFetchTasks = stores.Select(async store =>
        {
            List<DealItemDto> storeDeals = [];
            Exception? fetchError = null;

            await concurrencyLimiter.WaitAsync(ct);
            try
            {
                var rawDeals = await _shopperClient.GetDealsForStoreAsync(store.Id, store.PostalCode, store.Name, ct);

                // Deduplicate deals per-store so each physical store retains its own inventory.
                storeDeals = rawDeals
                    .GroupBy(d => !string.IsNullOrWhiteSpace(d.CleanName)
                        ? d.CleanName.Trim().ToLowerInvariant()
                        : d.ItemName.Trim().ToLowerInvariant())
                    .Where(g => !string.IsNullOrWhiteSpace(g.Key))
                    .Select(g =>
                    {
                        var best = g.OrderBy(d => d.DealPrice).ThenByDescending(d => d.ValueScore).First();
                        return new DealItemDto
                        {
                            DealId = $"{best.DealId}",
                            StoreId = store.Id,
                            StoreName = store.Name,
                            ItemName = best.ItemName,
                            CleanName = best.CleanName,
                            NormalizedCategory = best.NormalizedCategory,
                            PrimaryIngredient = best.PrimaryIngredient,
                            ProteinSubtype = best.ProteinSubtype,
                            ImageUrl = best.ImageUrl,
                            DealPrice = best.DealPrice,
                            OriginalPrice = best.OriginalPrice,
                            Currency = best.Currency,
                            Unit = best.Unit,
                            ValueScore = best.ValueScore
                        };
                    })
                    .ToList();
            }
            catch (Exception ex) when (!ct.IsCancellationRequested)
            {
                fetchError = ex;
                _logger.LogError(ex, "Failed to fetch deals for store {StoreId} ({StoreName}) in Job {JobId}.", store.Id, store.Name, jobId);
            }
            finally
            {
                concurrencyLimiter.Release();
            }

            await progressLock.WaitAsync(ct);
            try
            {
                if (fetchError == null)
                {
                    successfulStoreCount++;
                }

                await _jobStateStore.UpdateJobStatusAsync(
                    jobId,
                    JobStatus.FetchingDeals,
                    stageDescription: $"Fetching deals from stores ({successfulStoreCount}/{totalStoreCount})",
                    cancellationToken: ct);
            }
            finally
            {
                progressLock.Release();
            }

            return (Deals: storeDeals, Failed: fetchError != null, StoreId: store.Id);
        });

        var storeDealsResults = await Task.WhenAll(dealFetchTasks);
        var allDeals = storeDealsResults.SelectMany(result => result.Deals).ToList();
        var failedStoreIds = storeDealsResults
            .Where(result => result.Failed)
            .Select(result => result.StoreId)
            .ToList();

        var topDeals = new TopDealsResponse
        {
            Timestamp = DateTimeOffset.UtcNow,
            RegionContext = new RegionContextDto
            {
                Coordinates = new CoordinatesDto
                {
                    Latitude = 33.8895,
                    Longitude = -118.3533
                },
                StoreIds = stores.Select(s => s.Id).ToList()
            },
            Deals = allDeals
        };

        if (failedStoreIds.Count > 0)
        {
            _logger.LogWarning(
                "Retrieved deals from {SuccessfulStoreCount} of {StoreCount} stores for Job {JobId}; failures: {FailedStoreIds}.",
                successfulStoreCount,
                totalStoreCount,
                jobId,
                string.Join(", ", failedStoreIds));
        }

        _logger.LogInformation("Retrieved {DealCount} deals for job {JobId}.", topDeals.Deals.Count, jobId);
        return new DealFetchStageResult(topDeals, successfulStoreCount, failedStoreIds);
    }

    private static string GetDealFetchCompletionDescription(
        string successDescription,
        DealFetchStageResult dealFetchResult,
        int totalStoreCount)
    {
        if (dealFetchResult.FailedStoreIds.Count == 0)
        {
            return successDescription;
        }

        return $"{successDescription} Partial deal results: {dealFetchResult.SuccessfulStoreCount}/{totalStoreCount} stores succeeded; " +
               $"{dealFetchResult.FailedStoreIds.Count} failed ({string.Join(", ", dealFetchResult.FailedStoreIds)}).";
    }

    private async Task<MealPlanDraftResponse> GenerateMealPlanStageAsync(
        Guid jobId,
        List<String> cuisines,
        List<String> avoidIngredients,
        TopDealsResponse topDeals,
        Guid userId,
        CancellationToken ct,
        List<string>? dietaryPreferences = null,
        int daysCount = 3,
        int servingsCount = 2)
    {
        await _jobStateStore!.UpdateJobStatusAsync(
            jobId,
            JobStatus.GeneratingMealPlan,
            stageDescription: "Synthesizing customized recipes from curated deals...",
            cancellationToken: ct);

        var generateRequest = new GenerateMealPlanRequest
        {
            UserId = userId,
            Cuisines = cuisines ?? [],
            AvoidIngredients = avoidIngredients ?? [],
            TopDeals = topDeals.Deals ?? [],
            DietaryRestrictions = dietaryPreferences ?? [],
            DaysCount = daysCount,
            HouseholdSize = servingsCount
        };

        var draft = await _legacyPlanningClient!.GenerateMealPlanAsync(generateRequest, ct);

        _logger.LogInformation(
            "Generated meal plan {MealPlanId} with {MealCount} meals and {MissingCount} missing primary ingredients for Job {JobId}.",
            draft.MealPlanId,
            draft.Meals.Count,
            draft.MissingPrimaryIngredients.Count,
            jobId);

        return draft;
    }

    private async Task<List<MatchedIngredientDealDto>> ResolveMissingIngredientsStageAsync(
        Guid jobId,
        MealPlanDraftResponse draft,
        List<string> storeIds,
        CancellationToken ct)
    {
        if (draft.MissingPrimaryIngredients is not { Count: > 0 })
        {
            return [];
        }

        await _jobStateStore!.UpdateJobStatusAsync(
            jobId,
            JobStatus.GeneratingMealPlan,
            stageDescription: "Searching stores for secondary ingredients...",
            cancellationToken: ct);

        var secondaryMatches = await _shopperClient.LookupIngredientsAsync(storeIds, draft.MissingPrimaryIngredients, ct);
        if (secondaryMatches is not { Count: > 0 })
        {
            return [];
        }

        ApplyIngredientMatches(draft.Meals, secondaryMatches);
        return secondaryMatches;
    }

    private static void ApplyIngredientMatches(
        List<PlannedMealDto> meals,
        List<MatchedIngredientDealDto> matchedDeals)
    {
        var matchMap = matchedDeals
            .GroupBy(m => m.IngredientName, StringComparer.OrdinalIgnoreCase)
            .ToDictionary(g => g.Key, g => g.First(), StringComparer.OrdinalIgnoreCase);

        foreach (var meal in meals)
        {
            foreach (var ingredient in meal.Ingredients)
            {
                if (string.IsNullOrWhiteSpace(ingredient.DealId) &&
                    matchMap.TryGetValue(ingredient.Name, out var match))
                {
                    ingredient.DealId = match.DealId;
                    ingredient.StoreName = match.StoreName;
                    ingredient.IsPromotional = true;
                }
            }
        }
    }

    private MealPlanResultDto AssembleFinalResult(
        MealPlanDraftResponse draft,
        TopDealsResponse topDeals,
        List<MatchedIngredientDealDto> matchedDeals)
    {
        var dealLookup = BuildDealLookup(topDeals, matchedDeals);
        var recipeCards = BuildRecipeCards(draft.Meals, dealLookup, out var estimatedTotalTripCost);
        var requiredStores = ExtractRequiredStores(draft.Meals);
        var totalTravelTimeMinutes = 10 + (requiredStores.Count * 15);

        return new MealPlanResultDto
        {
            MealPlanId = draft.MealPlanId,
            EstimatedTotalTripCost = estimatedTotalTripCost,
            TotalTravelTimeMinutes = totalTravelTimeMinutes,
            RequiredStores = requiredStores,
            Recipes = recipeCards
        };
    }

    private Dictionary<string, DealPriceInfo> BuildDealLookup(
        TopDealsResponse topDeals,
        List<MatchedIngredientDealDto> matchedDeals)
    {
        var dealLookup = (topDeals.Deals ?? []).ToDictionary(
            d => d.DealId,
            d => new DealPriceInfo(d.DealPrice, d.Unit),
            StringComparer.OrdinalIgnoreCase);

        foreach (var matched in matchedDeals)
        {
            _logger.LogInformation("Matched deal {DealId}: {DealPrice} / {Unit}", matched.DealId, matched.DealPrice, matched.Unit);
            if (!dealLookup.ContainsKey(matched.DealId))
            {
                dealLookup[matched.DealId] = new DealPriceInfo(matched.DealPrice, matched.Unit);
            }
        }

        return dealLookup;
    }

    private static List<RecipeCardDto> BuildRecipeCards(
        List<PlannedMealDto> meals,
        Dictionary<string, DealPriceInfo> dealLookup,
        out decimal estimatedTotalTripCost)
    {
        estimatedTotalTripCost = 0m;
        var recipeCards = new List<RecipeCardDto>();

        foreach (var meal in meals)
        {
            var ingredientsWithDeals = new List<DisplayIngredientDto>();
            var pantryIngredients = new List<DisplayIngredientDto>();

            foreach (var ingredient in meal.Ingredients)
            {
                var hasDeal = !string.IsNullOrWhiteSpace(ingredient.StoreName) || !string.IsNullOrWhiteSpace(ingredient.DealId);
                var amountDesc = ingredient.Quantity;

                if (hasDeal)
                {
                    string? priceDesc = null;
                    if (!string.IsNullOrWhiteSpace(ingredient.DealId) && dealLookup.TryGetValue(ingredient.DealId, out var deal))
                    {
                        priceDesc = $"${deal.Price:F2} / {deal.Unit}";
                        var numericQty = ParseIngredientQuantity(amountDesc);
                        estimatedTotalTripCost += (numericQty * deal.Price);
                    }

                    ingredientsWithDeals.Add(new DisplayIngredientDto
                    {
                        Name = ingredient.Name,
                        AmountDescription = amountDesc ?? string.Empty,
                        StoreName = ingredient.StoreName,
                        DealPriceDescription = priceDesc,
                        IsPromotional = true
                    });
                }
                else
                {
                    pantryIngredients.Add(new DisplayIngredientDto
                    {
                        Name = ingredient.Name,
                        AmountDescription = amountDesc,
                        StoreName = null,
                        DealPriceDescription = null,
                        IsPromotional = false
                    });
                }
            }

            recipeCards.Add(new RecipeCardDto
            {
                RecipeId = !string.IsNullOrWhiteSpace(meal.MealId)
                    ? meal.MealId
                    : Guid.NewGuid().ToString(),
                RecipeTitle = meal.RecipeTitle,
                Description = meal.Description,
                ThumbnailUrl = null,
                IngredientsWithDeals = ingredientsWithDeals,
                PantryIngredients = pantryIngredients,
                Instructions = meal.Instructions ?? []
            });
        }

        return recipeCards;
    }

    private static decimal ParseIngredientQuantity(string? amountDesc)
    {
        var match = System.Text.RegularExpressions.Regex.Match(amountDesc ?? string.Empty, @"^-?\d+(\.\d+)?");
        if (match.Success && decimal.TryParse(match.Value, System.Globalization.NumberStyles.Any, System.Globalization.CultureInfo.InvariantCulture, out var parsedQty))
        {
            return parsedQty;
        }

        return 1.0m;
    }

    private static List<string> ExtractRequiredStores(List<PlannedMealDto> meals)
    {
        return meals
            .SelectMany(m => m.Ingredients)
            .Where(i => !string.IsNullOrWhiteSpace(i.StoreName))
            .Select(i => i.StoreName!)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToList();
    }
}
