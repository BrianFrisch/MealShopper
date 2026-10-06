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

    public MealPlanOrchestrator(
        IShopperClient shopperClient,
        IPlannerClient plannerClient,
        IPlanningClient planningClient,
        IJobStateStore jobStateStore,
        ILogger<MealPlanOrchestrator> logger)
    {
        _shopperClient = shopperClient ?? throw new ArgumentNullException(nameof(shopperClient));
        _plannerClient = plannerClient ?? throw new ArgumentNullException(nameof(plannerClient));
        _legacyPlanningClient = planningClient ?? throw new ArgumentNullException(nameof(planningClient));
        _jobStateStore = jobStateStore ?? throw new ArgumentNullException(nameof(jobStateStore));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
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
            RadiusMiles = request.RadiusMiles,
            MaxStores = request.MaxStores
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

            var topDeals = await FetchDealsStageAsync(job.JobId, candidateStores, ct);

            // 3. Generate Meal Plan
            if (_legacyPlanningClient == null)
            {
                return;
            }

            var payload = job.GetPayload<CreateMealPlanRequest>()!;
            var draft = await GenerateMealPlanStageAsync(job.JobId, payload.Cuisines, payload.AvoidIngredients, topDeals, ct);

            // 4. Phase 6 Loop-Back: Resolve missing primary ingredients
            var candidateStoreIds = candidateStores.Select(s => s.Id).ToList();
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
            var topDeals = await FetchDealsStageAsync(job.JobId, stores, ct);

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
                stageDescription: "Deals discovered successfully.",
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
                cancellationToken: ct);
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
            var topDeals = await _shopperClient.BatchLookupDealsAsync(payload.SelectedDealIds, payload.SelectedStoreIds, ct);

            var draft = await GenerateMealPlanStageAsync(job.JobId, payload.Cuisines, payload.AvoidIngredients, topDeals, ct);

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
        var radiusMiles = payload.SearchRadiusMiles;
        var maxStores = payload.MaxStores;

        var stores = await _shopperClient.DiscoverStoresAsync(lat, lon, radiusMiles, maxStores, ct);
        if (!string.IsNullOrWhiteSpace(address.ZipCode))
        {
            foreach (var store in stores)
            {
                if (string.IsNullOrWhiteSpace(store.PostalCode))
                {
                    store.PostalCode = address.ZipCode;
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

    private async Task<TopDealsResponse> FetchDealsStageAsync(
        Guid jobId,
        List<StoreDto> stores,
        CancellationToken ct)
    {
        await _jobStateStore!.UpdateJobStatusAsync(
            jobId,
            JobStatus.FetchingDeals,
            stageDescription: "Fetching circulars and scoring top promotional deals...",
            cancellationToken: ct);

        var dealFetchTasks = stores.Select(async store =>
        {
            var deals = await _shopperClient.GetDealsForStoreAsync(store.Id, store.PostalCode, store.Name, ct);
            foreach (var deal in deals)
            {
                if (string.IsNullOrWhiteSpace(deal.StoreId))
                {
                    deal.StoreId = store.Id;
                }
                if (string.IsNullOrWhiteSpace(deal.StoreName))
                {
                    deal.StoreName = store.Name;
                }
            }
            return deals;
        });
        var storeDealsResults = await Task.WhenAll(dealFetchTasks);

        var allDeals = storeDealsResults.SelectMany(deals => deals).ToList();

        // Deduplicate items by ItemName or CleanName keeping the best price/value score
        var dedupedDeals = allDeals
            .GroupBy(d => !string.IsNullOrWhiteSpace(d.CleanName)
                ? d.CleanName.Trim().ToLowerInvariant()
                : d.ItemName.Trim().ToLowerInvariant())
            .Where(g => !string.IsNullOrWhiteSpace(g.Key))
            .Select(g => g.OrderBy(d => d.DealPrice).ThenByDescending(d => d.ValueScore).First())
            .OrderByDescending(d => d.ValueScore)
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
            Deals = dedupedDeals
        };

        _logger.LogInformation("Retrieved {DealCount} deals for job {JobId}.", topDeals.Deals.Count, jobId);
        return topDeals;
    }

    private async Task<MealPlanDraftResponse> GenerateMealPlanStageAsync(
        Guid jobId,
        List<String> cuisines,
        List<String> avoidIngredients,
        TopDealsResponse topDeals,
        CancellationToken ct)
    {
        await _jobStateStore!.UpdateJobStatusAsync(
            jobId,
            JobStatus.GeneratingMealPlan,
            stageDescription: "Synthesizing customized recipes from curated deals...",
            cancellationToken: ct);

        var generateRequest = new GenerateMealPlanRequest
        {
            Cuisines = cuisines ?? [],
            AvoidIngredients = avoidIngredients ?? [],
            TopDeals = topDeals.Deals ?? []
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
                        DealPriceDescription = priceDesc
                    });
                }
                else
                {
                    pantryIngredients.Add(new DisplayIngredientDto
                    {
                        Name = ingredient.Name,
                        AmountDescription = amountDesc,
                        StoreName = null,
                        DealPriceDescription = null
                    });
                }
            }

            recipeCards.Add(new RecipeCardDto
            {
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
