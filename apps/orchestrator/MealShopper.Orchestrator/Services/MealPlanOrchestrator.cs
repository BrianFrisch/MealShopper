using MealShopper.Orchestrator.Clients;
using MealShopper.Orchestrator.Models;
using MealShopper.Orchestrator.Models.DTOs;
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

            // 4. Phase 6 Loop-Back: Resolve missing primary ingredients
            if (draft.MissingPrimaryIngredients is { Count: > 0 })
            {
                await _jobStateStore.UpdateJobStatusAsync(
                    jobId,
                    JobStatus.GeneratingMealPlan,
                    stageDescription: "Searching stores for secondary ingredients...",
                    cancellationToken: ct);

                var matchedDeals = await _shopperClient.LookupIngredientsAsync(storeIds, draft.MissingPrimaryIngredients, ct);

                if (matchedDeals is { Count: > 0 })
                {
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
                                ingredient.DealPrice = match.DealPrice;
                                if (!string.IsNullOrWhiteSpace(match.Unit) && string.IsNullOrWhiteSpace(ingredient.Unit))
                                {
                                    ingredient.Unit = match.Unit;
                                }
                            }
                        }
                    }
                }
            }

            // 5. Assemble Final Result (MealPlanResultDto)
            var recipeCards = new List<RecipeCardDto>();

            foreach (var meal in draft.Meals)
            {
                var ingredientsWithDeals = new List<DisplayIngredientDto>();
                var pantryIngredients = new List<DisplayIngredientDto>();

                foreach (var ingredient in meal.Ingredients)
                {
                    var hasDeal = !string.IsNullOrWhiteSpace(ingredient.StoreName) && ingredient.DealPrice.HasValue;
                    var amountDesc = string.IsNullOrWhiteSpace(ingredient.Unit)
                        ? $"{ingredient.Quantity}"
                        : $"{ingredient.Quantity} {ingredient.Unit}".Trim();

                    if (hasDeal)
                    {
                        var dealPriceDesc = string.IsNullOrWhiteSpace(ingredient.Unit)
                            ? $"${ingredient.DealPrice!.Value:F2}"
                            : $"${ingredient.DealPrice!.Value:F2} / {ingredient.Unit}";

                        ingredientsWithDeals.Add(new DisplayIngredientDto
                        {
                            Name = ingredient.Name,
                            AmountDescription = amountDesc,
                            StoreName = ingredient.StoreName,
                            DealPriceDescription = dealPriceDesc
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
                .Where(i => !string.IsNullOrWhiteSpace(i.StoreName) && i.DealPrice.HasValue)
                .Select(i => i.StoreName!)
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .ToList();

            var estimatedTotalTripCost = draft.Meals
                .SelectMany(m => m.Ingredients)
                .Where(i => !string.IsNullOrWhiteSpace(i.StoreName) && i.DealPrice.HasValue)
                .Sum(i => i.DealPrice!.Value * i.Quantity);

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
