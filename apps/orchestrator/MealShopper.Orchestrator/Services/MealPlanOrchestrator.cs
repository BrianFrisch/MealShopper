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

    // public MealPlanOrchestrator(
    //     IShopperClient shopperClient,
    //     IPlannerClient plannerClient,
    //     ILogger<MealPlanOrchestrator> logger)
    // {
    //     _shopperClient = shopperClient ?? throw new ArgumentNullException(nameof(shopperClient));
    //     _plannerClient = plannerClient ?? throw new ArgumentNullException(nameof(plannerClient));
    //     _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    // }

    public MealPlanOrchestrator(
        IJobStateStore jobStateStore,
        IShopperClient shopperClient,
        IPlanningClient planningClient,
        ILogger<MealPlanOrchestrator> logger)
    {
        _jobStateStore = jobStateStore ?? throw new ArgumentNullException(nameof(jobStateStore));
        _shopperClient = shopperClient ?? throw new ArgumentNullException(nameof(shopperClient));
        _legacyPlanningClient = planningClient ?? throw new ArgumentNullException(nameof(planningClient));
        _plannerClient = planningClient as IPlannerClient ?? new PlannerClient(new HttpClient(), Microsoft.Extensions.Logging.Abstractions.NullLogger<PlannerClient>.Instance);
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

        // Step 2: Extract store IDs and score deals
        var storeIds = discoveryRes.Stores.Select(s => s.Id).ToList();
        var scoringReq = new DealScoringRequest
        {
            StoreIds = storeIds,
            AvoidIngredients = request.AvoidIngredients ?? new List<string>(),
            TopN = 10
        };

        var scoringRes = await _shopperClient.ScoreDealsAsync(scoringReq, ct);
        var scoredDeals = scoringRes?.Deals ?? new List<DealDto>();

        _logger.LogInformation("Step 2 complete: Retrieved {DealCount} scored deals.", scoredDeals.Count);

        // Step 3: Generate meal plan
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

        // Step 4 (Loop-back): Match missing primary ingredients
        var matchedSecondaryDeals = new List<MatchedDealDto>();
        if (planRes?.MissingPrimaryIngredients is { Count: > 0 })
        {
            _logger.LogInformation(
                "Step 4 (Loop-back): Matching {MissingCount} missing primary ingredients across stores.",
                planRes.MissingPrimaryIngredients.Count);

            var matchReq = new IngredientMatchRequestDto
            {
                StoreIds = storeIds,
                MissingIngredients = planRes.MissingPrimaryIngredients,
                SimilarityThreshold = 65.0
            };

            var matchRes = await _shopperClient.MatchIngredientsAsync(matchReq, ct);
            if (matchRes?.Matches is { Count: > 0 })
            {
                matchedSecondaryDeals = matchRes.Matches;
            }

            _logger.LogInformation("Step 4 complete: Matched {MatchCount} secondary deals.", matchedSecondaryDeals.Count);
        }

        // Step 5: Consolidate and return
        var result = new ConsolidatedMealPlanResult(
            PlanId: planRes?.PlanId ?? string.Empty,
            SelectedStores: discoveryRes.Stores,
            Meals: planRes?.Meals ?? new List<MealShopper.Orchestrator.Models.Domain.PlannedMealDto>(),
            MatchedSecondaryDeals: matchedSecondaryDeals,
            EstimatedTotalSpend: planRes?.EstimatedTotalSpend ?? 0m,
            GeneratedAt: DateTimeOffset.UtcNow
        );

        _logger.LogInformation(
            "Step 5 complete: Consolidated meal plan result {PlanId} created successfully.",
            result.PlanId);

        return result;
    }

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
            await _jobStateStore.UpdateJobStatusAsync(
                jobId,
                JobStatus.DiscoveringStores,
                stageDescription: "Locating grocery stores within radius...",
                cancellationToken: ct);

            var address = job.RequestPayload.Address;
            var lat = address.Latitude ?? 33.894893;
            var lon = address.Longitude ?? -118.362658;
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

            var storeIds = stores.Select(s => (string)s.Id).ToList();
            var avoidIngredients = job.RequestPayload.AvoidIngredients;

            var topDeals = await _shopperClient.GetTopDealsAsync(storeIds, avoidIngredients, ct);
            _logger.LogInformation("Retrieved {DealCount} deals for job {JobId}.", topDeals.Deals.Count, jobId);

            // 3. Generate Meal Plan
            await _jobStateStore.UpdateJobStatusAsync(
                jobId,
                JobStatus.GeneratingMealPlan,
                stageDescription: "Synthesizing customized recipes from curated deals...",
                cancellationToken: ct);

            if (_legacyPlanningClient != null)
            {
                var generateRequest = new GenerateMealPlanRequest
                {
                    Cuisines = job.RequestPayload.Cuisines ?? [],
                    AvoidIngredients = job.RequestPayload.AvoidIngredients ?? [],
                    TopDeals = topDeals.Deals ?? []
                };

                var draft = await _legacyPlanningClient.GenerateMealPlanAsync(generateRequest, ct);

                _logger.LogInformation(
                    "Generated meal plan {MealPlanId} with {MealCount} meals and {MissingCount} missing primary ingredients for Job {JobId}.",
                    draft.MealPlanId,
                    draft.Meals.Count,
                    draft.MissingPrimaryIngredients.Count,
                    jobId);

                // 4. Phase 6 Loop-Back: Resolve missing primary ingredients
                var matchedDeals = new List<MatchedIngredientDealDto>();
                if (draft.MissingPrimaryIngredients is { Count: > 0 })
                {
                    await _jobStateStore.UpdateJobStatusAsync(
                        jobId,
                        JobStatus.GeneratingMealPlan,
                        stageDescription: "Searching stores for secondary ingredients...",
                        cancellationToken: ct);

                    var secondaryMatches = await _shopperClient.LookupIngredientsAsync(storeIds, draft.MissingPrimaryIngredients, ct);

                    if (secondaryMatches is { Count: > 0 })
                    {
                        matchedDeals = secondaryMatches;
                        var matchMap = matchedDeals
                            .GroupBy(m => m.IngredientName, StringComparer.OrdinalIgnoreCase)
                            .ToDictionary(g => g.Key, g => g.First(), StringComparer.OrdinalIgnoreCase);

                        foreach (var meal in draft.Meals)
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
                }

                // 5. Assemble Final Result (MealPlanResultDto)
                var recipeCards = new List<RecipeCardDto>();

                // Build a fast lookup dictionary of all circular deals & matched secondary deals
                // var dealLookup = topDeals.Deals.ToDictionary(d => d.DealId, StringComparer.OrdinalIgnoreCase);
                var dealLookup = (topDeals.Deals ?? []).ToDictionary(
                    d => d.DealId, 
                    d => new { Price = d.DealPrice, Unit = d.Unit }, 
                    StringComparer.OrdinalIgnoreCase);
                    
                // Merge secondary matched deals so loop-back items get priced and factored into trip cost
                foreach (var matched in matchedDeals)
                {
                    _logger.LogInformation("Matched deal {DealId}: {DealPrice} / {Unit}", matched.DealId, matched.DealPrice, matched.Unit);
                    if (!dealLookup.ContainsKey(matched.DealId))
                    {
                        dealLookup[matched.DealId] = new { Price = matched.DealPrice, Unit = matched.Unit };
                    }
                }

                decimal estimatedTotalTripCost = 0m;

                foreach (var meal in draft.Meals)
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

                                // Extract numeric quantity (e.g., "1.5 lbs" -> 1.5, "1" -> 1)
                                var numericQty = 1.0m;
                                var match = System.Text.RegularExpressions.Regex.Match(amountDesc ?? string.Empty, @"^-?\d+(\.\d+)?");
                                if (match.Success && decimal.TryParse(match.Value, System.Globalization.NumberStyles.Any, System.Globalization.CultureInfo.InvariantCulture, out var parsedQty))
                                {
                                    numericQty = parsedQty;
                                }

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

                var requiredStores = draft.Meals
                    .SelectMany(m => m.Ingredients)
                    .Where(i => !string.IsNullOrWhiteSpace(i.StoreName))
                    .Select(i => i.StoreName!)
                    .Distinct(StringComparer.OrdinalIgnoreCase)
                    .ToList();

                var totalTravelTimeMinutes = 10 + (requiredStores.Count * 15);

                var finalResultDto = new MealPlanResultDto
                {
                    MealPlanId = draft.MealPlanId,
                    EstimatedTotalTripCost = estimatedTotalTripCost,
                    TotalTravelTimeMinutes = totalTravelTimeMinutes,
                    RequiredStores = requiredStores,
                    Recipes = recipeCards
                };

                // 6. Transition Job to Completed
                await _jobStateStore.CompleteJobAsync(jobId, finalResultDto, ct);

                _logger.LogInformation(
                    "Completed meal plan generation for Job {JobId}. Total Cost: {TotalCost:C}, Recipes Count: {RecipeCount}, Required Stores: {StoreCount}.",
                    jobId,
                    finalResultDto.EstimatedTotalTripCost,
                    finalResultDto.Recipes.Count,
                    finalResultDto.RequiredStores.Count);
            }
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
