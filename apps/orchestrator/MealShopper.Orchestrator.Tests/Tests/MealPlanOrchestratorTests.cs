using FluentAssertions;
using MealShopper.Orchestrator.Clients;
using MealShopper.Orchestrator.Exceptions;
using MealShopper.Orchestrator.Models;
using MealShopper.Orchestrator.Models.Domain;
using MealShopper.Orchestrator.Models.DTOs;
using MealShopper.Orchestrator.Models.Planner;
using MealShopper.Orchestrator.Services;
using MealShopper.Orchestrator.Tests.Helpers;
using Microsoft.Extensions.Logging.Abstractions;
using Moq;

namespace MealShopper.Orchestrator.Tests.Tests;

public class MealPlanOrchestratorTests
{
    #region ExecuteWorkflowAsync Tests

    [Fact]
    public async Task ExecuteWorkflowAsync_SuccessfullyExecutesAllStepsAndReturnsConsolidatedResult()
    {
        // Arrange
        var mockShopper = new Mock<IShopperClient>();
        var mockPlanner = new Mock<IPlannerClient>();

        var stores = new List<StoreDto>
        {
            new() { Id = "store-1", Name = "Store 1", Street = "123 Main St", City = "LA", State = "CA", ZipCode = "90001", DistanceMiles = 1.2 },
            new() { Id = "store-2", Name = "Store 2", Street = "456 Oak St", City = "LA", State = "CA", ZipCode = "90002", DistanceMiles = 2.5 }
        };

        mockShopper
            .Setup(s => s.DiscoverStoresAsync(It.IsAny<StoreDiscoveryRequest>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(new StoreDiscoveryResponse { Stores = stores, TotalFound = 2 });

        var scoredDeals = new List<DealDto>
        {
            new() { DealId = "deal-1", StoreId = "store-1", StoreName = "Store 1", ItemName = "Chicken", Price = 4.99m, Unit = "lb", PrimaryIngredient = "chicken" }
        };

        mockShopper
            .Setup(s => s.ScoreDealsAsync(It.Is<DealScoringRequest>(r => r.StoreIds.Count == 2), It.IsAny<CancellationToken>()))
            .ReturnsAsync(new DealScoringResponse { Deals = scoredDeals, TotalScored = 1 });

        var plannedMeals = new List<PlannedMealDto>
        {
            new()
            {
                MealId = "meal-1",
                RecipeName = "Chicken Bowl",
                Description = "Tasty chicken bowl",
                EstimatedPrepTimeMinutes = 30,
                Servings = 4,
                Ingredients = new List<RecipeIngredientDto>
                {
                    new() { Name = "Chicken", Quantity = "1 lb", IsPromotional = true, DealId = "deal-1", StoreName = "Store 1" },
                    new() { Name = "Rice", Quantity = "2 cups", IsPromotional = false }
                },
                Instructions = new List<string> { "Cook rice", "Cook chicken", "Combine" }
            }
        };

        mockPlanner
            .Setup(p => p.GeneratePlanAsync(It.Is<MealPlanRequestDto>(r => r.ScoredDeals.Count == 1 && r.HouseholdSize == 4 && r.TargetMealCount == 3), It.IsAny<CancellationToken>()))
            .ReturnsAsync(new MealPlanResponseDto
            {
                PlanId = "plan-abc-123",
                Meals = plannedMeals,
                MissingPrimaryIngredients = new List<string> { "Rice" },
                EstimatedTotalSpend = 14.50m
            });

        var matchedDeals = new List<MatchedDealDto>
        {
            new() { MissingIngredient = "Rice", DealId = "deal-rice-2", StoreId = "store-2", StoreName = "Store 2", ItemName = "Jasmine Rice", Price = 3.50m, Unit = "bag", SimilarityScore = 95.0 }
        };

        mockShopper
            .Setup(s => s.MatchIngredientsAsync(It.Is<IngredientMatchRequestDto>(r => r.MissingIngredients.Contains("Rice") && r.StoreIds.Count == 2), It.IsAny<CancellationToken>()))
            .ReturnsAsync(new IngredientMatchResponseDto { Matches = matchedDeals, TotalMatched = 1 });

        var orchestrator = new MealPlanOrchestrator(
            mockShopper.Object,
            mockPlanner.Object,
            Mock.Of<IPlanningClient>(),
            Mock.Of<IJobStateStore>(),
            NullLogger<MealPlanOrchestrator>.Instance,
            Mock.Of<IGeocodingService>());

        var request = new PlanGenerationWorkflowRequest(
            Latitude: 34.0522,
            Longitude: -118.2437,
            RadiusMiles: 5.0,
            HouseholdSize: 4,
            TargetMealCount: 3,
            PreferredCuisines: new List<string> { "Mexican", "Asian" },
            DietaryRestrictions: new List<string> { "Nut-Free" },
            AvoidIngredients: new List<string> { "Peanuts" }
        );

        // Act
        var result = await orchestrator.ExecuteWorkflowAsync(request);

        // Assert
        result.Should().NotBeNull();
        result.PlanId.Should().Be("plan-abc-123");
        result.SelectedStores.Should().HaveCount(2);
        result.SelectedStores[0].Name.Should().Be("Store 1");
        result.SelectedStores[1].Name.Should().Be("Store 2");
        result.Meals.Should().HaveCount(1);
        result.Meals[0].RecipeName.Should().Be("Chicken Bowl");
        result.MatchedSecondaryDeals.Should().HaveCount(1);
        result.MatchedSecondaryDeals[0].ItemName.Should().Be("Jasmine Rice");
        result.EstimatedTotalSpend.Should().Be(14.50m);
        result.GeneratedAt.Should().BeCloseTo(DateTimeOffset.UtcNow, TimeSpan.FromSeconds(5));

        mockShopper.Verify(s => s.DiscoverStoresAsync(It.Is<StoreDiscoveryRequest>(r => r.Latitude == 34.0522), It.IsAny<CancellationToken>()), Times.Once);
        mockShopper.Verify(s => s.ScoreDealsAsync(It.Is<DealScoringRequest>(r => r.AvoidIngredients.Contains("Peanuts")), It.IsAny<CancellationToken>()), Times.Once);
        mockPlanner.Verify(p => p.GeneratePlanAsync(It.Is<MealPlanRequestDto>(r => r.PreferredCuisines.Contains("Mexican") && r.DietaryRestrictions.Contains("Nut-Free")), It.IsAny<CancellationToken>()), Times.Once);
        mockShopper.Verify(s => s.MatchIngredientsAsync(It.Is<IngredientMatchRequestDto>(r => r.MissingIngredients.Contains("Rice")), It.IsAny<CancellationToken>()), Times.Once);
    }

    [Fact]
    public async Task ExecuteWorkflowAsync_ThrowsDomainException_WhenNoStoresFound()
    {
        // Arrange
        var mockShopper = new Mock<IShopperClient>();
        var mockPlanner = new Mock<IPlannerClient>();

        mockShopper
            .Setup(s => s.DiscoverStoresAsync(It.IsAny<StoreDiscoveryRequest>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(new StoreDiscoveryResponse { Stores = new List<StoreDto>(), TotalFound = 0 });

        var orchestrator = new MealPlanOrchestrator(
            mockShopper.Object,
            mockPlanner.Object,
            Mock.Of<IPlanningClient>(),
            Mock.Of<IJobStateStore>(),
            NullLogger<MealPlanOrchestrator>.Instance,
            Mock.Of<IGeocodingService>());

        var request = new PlanGenerationWorkflowRequest(
            Latitude: 34.0522,
            Longitude: -118.2437,
            RadiusMiles: 2.0,
            HouseholdSize: 2,
            TargetMealCount: 3,
            PreferredCuisines: new List<string>(),
            DietaryRestrictions: new List<string>(),
            AvoidIngredients: new List<string>()
        );

        // Act
        var act = () => orchestrator.ExecuteWorkflowAsync(request);

        // Assert
        var exception = await act.Should().ThrowAsync<DomainException>();
        exception.WithMessage("No stores within radius");

        mockShopper.Verify(s => s.ScoreDealsAsync(It.IsAny<DealScoringRequest>(), It.IsAny<CancellationToken>()), Times.Never);
        mockPlanner.Verify(p => p.GeneratePlanAsync(It.IsAny<MealPlanRequestDto>(), It.IsAny<CancellationToken>()), Times.Never);
    }

    [Fact]
    public async Task ExecuteWorkflowAsync_SkipsLoopBack_WhenNoMissingPrimaryIngredients()
    {
        // Arrange
        var mockShopper = new Mock<IShopperClient>();
        var mockPlanner = new Mock<IPlannerClient>();

        mockShopper
            .Setup(s => s.DiscoverStoresAsync(It.IsAny<StoreDiscoveryRequest>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(new StoreDiscoveryResponse
            {
                Stores = new List<StoreDto> { new() { Id = "store-1", Name = "Store 1" } },
                TotalFound = 1
            });

        mockShopper
            .Setup(s => s.ScoreDealsAsync(It.IsAny<DealScoringRequest>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(new DealScoringResponse { Deals = new List<DealDto>(), TotalScored = 0 });

        mockPlanner
            .Setup(p => p.GeneratePlanAsync(It.IsAny<MealPlanRequestDto>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(new MealPlanResponseDto
            {
                PlanId = "plan-complete",
                Meals = new List<PlannedMealDto>(),
                MissingPrimaryIngredients = new List<string>(),
                EstimatedTotalSpend = 20.00m
            });

        var orchestrator = new MealPlanOrchestrator(
            mockShopper.Object,
            mockPlanner.Object,
            Mock.Of<IPlanningClient>(),
            Mock.Of<IJobStateStore>(),
            NullLogger<MealPlanOrchestrator>.Instance,
            Mock.Of<IGeocodingService>());

        var request = new PlanGenerationWorkflowRequest(
            Latitude: 34.0,
            Longitude: -118.0,
            RadiusMiles: 5.0,
            HouseholdSize: 2,
            TargetMealCount: 2,
            PreferredCuisines: new List<string>(),
            DietaryRestrictions: new List<string>(),
            AvoidIngredients: new List<string>()
        );

        // Act
        var result = await orchestrator.ExecuteWorkflowAsync(request);

        // Assert
        result.Should().NotBeNull();
        result.PlanId.Should().Be("plan-complete");
        result.MatchedSecondaryDeals.Should().BeEmpty();

        mockShopper.Verify(s => s.MatchIngredientsAsync(It.IsAny<IngredientMatchRequestDto>(), It.IsAny<CancellationToken>()), Times.Never);
    }

    #endregion

    [Fact]
    public async Task ProcessJobAsync_ProgressesThroughStagesAndCompletesCleanly()
    {
        // Arrange
        var underlyingStore = new InMemoryJobTracker();
        var recordedTransitions = new List<(JobStatus Status, string? StageDescription)>();

        var jobStore = new TrackingJobStateStore(underlyingStore, transition =>
        {
            recordedTransitions.Add(transition);
        });

        var mockHandler = new MockHttpMessageHandler();

        var shopperHttpClient = new HttpClient(mockHandler)
        {
            BaseAddress = new Uri("http://localhost:8001/")
        };
        var shopperClient = new ShopperClient(shopperHttpClient, NullLogger<ShopperClient>.Instance);

        var plannerHttpClient = new HttpClient(mockHandler)
        {
            BaseAddress = new Uri("http://localhost:8002/")
        };
        var planningClient = new PlanningClient(plannerHttpClient, NullLogger<PlanningClient>.Instance);

        var orchestrator = new MealPlanOrchestrator(
            shopperClient,
            Mock.Of<IPlannerClient>(),
            planningClient,
            jobStore,
            NullLogger<MealPlanOrchestrator>.Instance,
            Mock.Of<IGeocodingService>());

        var jobId = Guid.NewGuid();
        var initialJob = new JobRecord
        {
            JobId = jobId,
            Status = JobStatus.Pending,
            RequestPayload = new CreateMealPlanRequest
            {
                Cuisines = new List<string> { "Mexican", "Italian" },
                AvoidIngredients = new List<string> { "peanuts" },
                Address = new AddressDto
                {
                    ZipCode = "90250",
                    Latitude = 33.8958,
                    Longitude = -118.3531
                },
                SearchRadiusMiles = 5
            }
        };

        await jobStore.CreateJobAsync(initialJob);

        // Act
        await orchestrator.ProcessJobAsync(jobId);

        // Assert
        var finalJob = await jobStore.GetJobAsync(jobId);
        finalJob.Should().NotBeNull();
        finalJob!.Status.Should().Be(JobStatus.Completed);
        finalJob.ErrorMessage.Should().BeNull();
        finalJob.Result.Should().NotBeNull();
        finalJob.Result!.MealPlanId.Should().Be("plan-draft-20260908-001");
        finalJob.Result.Recipes.Should().HaveCount(2);
        finalJob.Result.RequiredStores.Should().NotBeEmpty();
        finalJob.Result.EstimatedTotalTripCost.Should().BeGreaterThan(0);
        finalJob.Result.TotalTravelTimeMinutes.Should().Be(10 + (finalJob.Result.RequiredStores.Count * 15));

        // Verify status progression: Pending -> DiscoveringStores -> FetchingDeals -> GeneratingMealPlan -> (LoopBack GeneratingMealPlan) -> Completed
        var statuses = recordedTransitions.Select(t => t.Status).ToList();
        statuses.Should().ContainInOrder(
            JobStatus.Pending,
            JobStatus.DiscoveringStores,
            JobStatus.FetchingDeals,
            JobStatus.GeneratingMealPlan,
            JobStatus.Completed);

        // Verify that stores, deals (for 2 stores), planner, and loopback lookup requests were captured
        mockHandler.CapturedRequests.Should().HaveCount(5);
        mockHandler.CapturedRequests[0].RequestUri!.ToString().Should().Contain("v1/shopper/stores");
        mockHandler.CapturedRequests.Should().Contain(r => r.RequestUri!.ToString().Contains("v1/deals/stores/store_vons_1"));
        mockHandler.CapturedRequests.Should().Contain(r => r.RequestUri!.ToString().Contains("v1/deals/stores/store_grocoutlet_1"));
        mockHandler.CapturedRequests.Should().Contain(r => r.RequestUri!.ToString().Contains("v1/planner/generate"));
        mockHandler.CapturedRequests.Should().Contain(r => r.RequestUri!.ToString().Contains("v1/shopper/lookup-ingredients"));
    }

    private class TrackingJobStateStore : IJobStateStore
    {
        private readonly IJobStateStore _inner;
        private readonly Action<(JobStatus Status, string? StageDescription)> _onStatusRecorded;

        public TrackingJobStateStore(
            IJobStateStore inner,
            Action<(JobStatus Status, string? StageDescription)> onStatusRecorded)
        {
            _inner = inner;
            _onStatusRecorded = onStatusRecorded;
        }

        public async Task<JobRecord> CreateJobAsync(JobRecord job, CancellationToken cancellationToken = default)
        {
            _onStatusRecorded((job.Status, job.StageDescription));
            return await _inner.CreateJobAsync(job, cancellationToken);
        }

        public Task<JobRecord?> GetJobAsync(Guid jobId, CancellationToken cancellationToken = default)
        {
            return _inner.GetJobAsync(jobId, cancellationToken);
        }

        public async Task<JobRecord?> UpdateJobStatusAsync(
            Guid jobId,
            JobStatus status,
            string? errorMessage = null,
            string? stageDescription = null,
            CancellationToken cancellationToken = default)
        {
            _onStatusRecorded((status, stageDescription));
            return await _inner.UpdateJobStatusAsync(jobId, status, errorMessage, stageDescription, cancellationToken);
        }

        public async Task<JobRecord?> CompleteJobAsync<T>(
            Guid jobId,
            T result,
            string? stageDescription = "Completed successfully.",
            CancellationToken cancellationToken = default)
        {
            _onStatusRecorded((JobStatus.Completed, stageDescription));
            return await _inner.CompleteJobAsync(jobId, result, stageDescription, cancellationToken);
        }
    }

    [Fact]
    public async Task ProcessJobAsync_WhenShopperServiceFails_UpdatesStatusToFailed()
    {
        // Arrange
        var jobStore = new InMemoryJobTracker();
        var mockHandler = new MockHttpMessageHandler();
        mockHandler.SetServerError("Shopper store discovery service unavailable");

        var shopperHttpClient = new HttpClient(mockHandler)
        {
            BaseAddress = new Uri("http://localhost:8001/")
        };
        var shopperClient = new ShopperClient(shopperHttpClient, NullLogger<ShopperClient>.Instance);

        var plannerHttpClient = new HttpClient(mockHandler)
        {
            BaseAddress = new Uri("http://localhost:8002/")
        };
        var planningClient = new PlanningClient(plannerHttpClient, NullLogger<PlanningClient>.Instance);

        var orchestrator = new MealPlanOrchestrator(
            shopperClient,
            Mock.Of<IPlannerClient>(),
            planningClient,
            jobStore,
            NullLogger<MealPlanOrchestrator>.Instance,
            Mock.Of<IGeocodingService>()    );

        var jobId = Guid.NewGuid();
        var initialJob = new JobRecord
        {
            JobId = jobId,
            Status = JobStatus.Pending,
            RequestPayload = new CreateMealPlanRequest
            {
                Address = new AddressDto
                {
                    ZipCode = "90250"
                }
            }
        };

        await jobStore.CreateJobAsync(initialJob);

        // Act
        await orchestrator.ProcessJobAsync(jobId);

        // Assert
        var finalJob = await jobStore.GetJobAsync(jobId);
        finalJob.Should().NotBeNull();
        finalJob!.Status.Should().Be(JobStatus.Failed);
        finalJob.ErrorMessage.Should().Contain("Shopper store discovery service unavailable");
        finalJob.StageDescription.Should().Be("Workflow failed.");
    }

    [Fact]
    public async Task ProcessJobAsync_WhenPlanningServiceFails_UpdatesStatusToFailed()
    {
        // Arrange
        var jobStore = new InMemoryJobTracker();
        var mockHandler = new MockHttpMessageHandler();

        var shopperHttpClient = new HttpClient(mockHandler)
        {
            BaseAddress = new Uri("http://localhost:8001/")
        };
        var shopperClient = new ShopperClient(shopperHttpClient, NullLogger<ShopperClient>.Instance);

        var plannerHttpClient = new HttpClient(mockHandler)
        {
            BaseAddress = new Uri("http://localhost:8002/")
        };
        var planningClient = new PlanningClient(plannerHttpClient, NullLogger<PlanningClient>.Instance);

        // Fail only the planner endpoint
        mockHandler.CustomHandler = req =>
        {
            if (req.RequestUri != null && req.RequestUri.ToString().Contains("v1/planner/generate"))
            {
                return new HttpResponseMessage(System.Net.HttpStatusCode.InternalServerError)
                {
                    Content = new StringContent("Planning service failed to generate recipe", System.Text.Encoding.UTF8, "application/json")
                };
            }
            return null;
        };

        var orchestrator = new MealPlanOrchestrator(
            shopperClient,
            Mock.Of<IPlannerClient>(),
            planningClient,
            jobStore,
            NullLogger<MealPlanOrchestrator>.Instance,
            Mock.Of<IGeocodingService>());

        var jobId = Guid.NewGuid();
        var initialJob = new JobRecord
        {
            JobId = jobId,
            Status = JobStatus.Pending,
            RequestPayload = new CreateMealPlanRequest
            {
                Cuisines = new List<string> { "Mexican" },
                Address = new AddressDto
                {
                    ZipCode = "90250"
                }
            }
        };

        await jobStore.CreateJobAsync(initialJob);

        // Act
        await orchestrator.ProcessJobAsync(jobId);

        // Assert
        var finalJob = await jobStore.GetJobAsync(jobId);
        finalJob.Should().NotBeNull();
        finalJob!.Status.Should().Be(JobStatus.Failed);
        finalJob.ErrorMessage.Should().Contain("Planning service failed to generate recipe");
        finalJob.StageDescription.Should().Be("Workflow failed.");
    }

    [Fact]
    public async Task ProcessJobAsync_WhenDraftHasMissingIngredients_PerformsLoopBackAndMergesDeals()
    {
        // Arrange
        var jobStore = new InMemoryJobTracker();
        var mockHandler = new MockHttpMessageHandler();

        var shopperHttpClient = new HttpClient(mockHandler)
        {
            BaseAddress = new Uri("http://localhost:8001/")
        };
        var shopperClient = new ShopperClient(shopperHttpClient, NullLogger<ShopperClient>.Instance);

        var plannerHttpClient = new HttpClient(mockHandler)
        {
            BaseAddress = new Uri("http://localhost:8002/")
        };
        var planningClient = new PlanningClient(plannerHttpClient, NullLogger<PlanningClient>.Instance);

        var orchestrator = new MealPlanOrchestrator(
            shopperClient,
            Mock.Of<IPlannerClient>(),
            planningClient,
            jobStore,
            NullLogger<MealPlanOrchestrator>.Instance,
            Mock.Of<IGeocodingService>());

        var jobId = Guid.NewGuid();
        var initialJob = new JobRecord
        {
            JobId = jobId,
            Status = JobStatus.Pending,
            RequestPayload = new CreateMealPlanRequest
            {
                Cuisines = new List<string> { "Mexican" },
                Address = new AddressDto { ZipCode = "90250" }
            }
        };

        await jobStore.CreateJobAsync(initialJob);

        // Act
        await orchestrator.ProcessJobAsync(jobId);

        // Assert
        var finalJob = await jobStore.GetJobAsync(jobId);
        finalJob.Should().NotBeNull();
        finalJob!.Status.Should().Be(JobStatus.Completed);
        finalJob.Result.Should().NotBeNull();

        var result = finalJob.Result!;
        result.Recipes.Should().HaveCount(2);

        // First recipe: Lemon Pepper Chicken (Olive Oil was missing and loop-back matched)
        var chickenRecipe = result.Recipes.First(r => r.RecipeTitle == "Lemon Pepper Chicken");
        chickenRecipe.IngredientsWithDeals.Should().Contain(i => i.Name == "Olive Oil" && i.StoreName == "Grocery Outlet");
        chickenRecipe.IngredientsWithDeals.Should().Contain(i => i.Name == "Boneless Skinless Chicken Breast" && i.StoreName == "Ralphs");
        chickenRecipe.PantryIngredients.Should().Contain(i => i.Name == "Lemon Pepper Seasoning" && i.StoreName == null && i.DealPriceDescription == null);

        // Second recipe: Street Tacos (Ground Beef was missing and loop-back matched with Vons)
        var tacosRecipe = result.Recipes.First(r => r.RecipeTitle == "Street Tacos");
        tacosRecipe.IngredientsWithDeals.Should().Contain(i => i.Name == "Ground Beef (85/15)" && i.StoreName == "Vons");
        tacosRecipe.IngredientsWithDeals.Should().Contain(i => i.Name == "Corn Tortillas (12 count)" && i.StoreName == "Trader Joe's");
        tacosRecipe.IngredientsWithDeals.Should().Contain(i => i.Name == "Organic Red Bell Peppers" && i.StoreName == "Sprouts Farmers Market");
        tacosRecipe.PantryIngredients.Should().Contain(i => i.Name == "Taco Seasoning" && i.StoreName == null && i.DealPriceDescription == null);

        // Required stores should include Ralphs, Sprouts, Trader Joe's, Grocery Outlet, and Vons
        result.RequiredStores.Should().Contain("Vons");
        result.RequiredStores.Should().Contain("Grocery Outlet");
        result.EstimatedTotalTripCost.Should().BeGreaterThan(0);
        result.TotalTravelTimeMinutes.Should().Be(10 + (result.RequiredStores.Count * 15));
    }

    [Fact]
    public async Task ProcessJobAsync_EndToEndPipeline_SuccessfullyCompletesWithPartitionedIngredientsAndRequiredStores()
    {
        // Arrange
        var jobStore = new InMemoryJobTracker();
        var mockHandler = new MockHttpMessageHandler();

        var shopperHttpClient = new HttpClient(mockHandler)
        {
            BaseAddress = new Uri("http://localhost:8001/")
        };
        var shopperClient = new ShopperClient(shopperHttpClient, NullLogger<ShopperClient>.Instance);

        var plannerHttpClient = new HttpClient(mockHandler)
        {
            BaseAddress = new Uri("http://localhost:8002/")
        };
        var planningClient = new PlanningClient(plannerHttpClient, NullLogger<PlanningClient>.Instance);

        var orchestrator = new MealPlanOrchestrator(
            shopperClient,
            Mock.Of<IPlannerClient>(),
            planningClient,
            jobStore,
            NullLogger<MealPlanOrchestrator>.Instance,
            Mock.Of<IGeocodingService>());

        var jobId = Guid.NewGuid();
        var pendingJob = new JobRecord
        {
            JobId = jobId,
            Status = JobStatus.Pending,
            RequestPayload = new CreateMealPlanRequest
            {
                Cuisines = new List<string> { "Mexican", "American" },
                AvoidIngredients = new List<string> { "peanuts" },
                Address = new AddressDto
                {
                    ZipCode = "90250",
                    Latitude = 34.053625,
                    Longitude = -118.243007
                },
                SearchRadiusMiles = 5
            }
        };

        await jobStore.CreateJobAsync(pendingJob);

        // Act
        await orchestrator.ProcessJobAsync(jobId);

        // Assert
        var completedJob = await jobStore.GetJobAsync(jobId);
        completedJob.Should().NotBeNull();
        completedJob!.Status.Should().Be(JobStatus.Completed);
        completedJob.ErrorMessage.Should().BeNull();
        completedJob.Result.Should().NotBeNull();

        var result = completedJob.Result!;
        result.MealPlanId.Should().NotBeNullOrWhiteSpace();
        result.EstimatedTotalTripCost.Should().BeGreaterThan(0);
        result.TotalTravelTimeMinutes.Should().BeGreaterThan(0);

        // Assert job.Result.RequiredStores contains expected stores ("Vons", "Grocery Outlet")
        result.RequiredStores.Should().Contain("Vons");
        result.RequiredStores.Should().Contain("Grocery Outlet");

        // Assert each recipe has ingredients partitioned correctly into deals and pantry items
        result.Recipes.Should().NotBeEmpty();
        foreach (var recipe in result.Recipes)
        {
            recipe.RecipeTitle.Should().NotBeNullOrWhiteSpace();
            recipe.Instructions.Should().NotBeEmpty();

            // Deals ingredients must have valid store info
            recipe.IngredientsWithDeals.Should().NotBeEmpty();
            foreach (var dealIngredient in recipe.IngredientsWithDeals)
            {
                dealIngredient.Name.Should().NotBeNullOrWhiteSpace();
                dealIngredient.AmountDescription.Should().NotBeNullOrWhiteSpace();
                dealIngredient.StoreName.Should().NotBeNullOrWhiteSpace();
            }

            // Pantry ingredients must have null store and price descriptions
            recipe.PantryIngredients.Should().NotBeEmpty();
            foreach (var pantryIngredient in recipe.PantryIngredients)
            {
                pantryIngredient.Name.Should().NotBeNullOrWhiteSpace();
                pantryIngredient.AmountDescription.Should().NotBeNullOrWhiteSpace();
                pantryIngredient.StoreName.Should().BeNull();
                pantryIngredient.DealPriceDescription.Should().BeNull();
            }
        }
    }

    #region ProcessDiscoveryJobAsync Tests

    [Fact]
    public async Task ProcessDiscoveryJobAsync_ProgressesThroughStagesAndCompletesWithoutPlanning()
    {
        // Arrange
        var underlyingStore = new InMemoryJobTracker();
        var recordedTransitions = new List<(JobStatus Status, string? StageDescription)>();

        var jobStore = new TrackingJobStateStore(underlyingStore, transition =>
        {
            recordedTransitions.Add(transition);
        });

        var mockHandler = new MockHttpMessageHandler();

        var shopperHttpClient = new HttpClient(mockHandler)
        {
            BaseAddress = new Uri("http://localhost:8001/")
        };
        var shopperClient = new ShopperClient(shopperHttpClient, NullLogger<ShopperClient>.Instance);

        var mockPlanningClient = new Mock<IPlanningClient>();

        var orchestrator = new MealPlanOrchestrator(
            shopperClient,
            Mock.Of<IPlannerClient>(),
            mockPlanningClient.Object,
            jobStore,
            NullLogger<MealPlanOrchestrator>.Instance,
            Mock.Of<IGeocodingService>());

        var jobId = Guid.NewGuid();
        var initialJob = new JobRecord
        {
            JobId = jobId,
            JobType = JobType.StoreDiscovery,
            Status = JobStatus.Pending,
            RequestPayload = new CreateMealPlanRequest
            {
                Address = new AddressDto
                {
                    ZipCode = "90250",
                    Latitude = 33.8958,
                    Longitude = -118.3531
                },
                SearchRadiusMiles = 5
            }
        };

        await jobStore.CreateJobAsync(initialJob);

        // Act
        await orchestrator.ProcessDiscoveryJobAsync(jobId);

        // Assert
        var finalJob = await jobStore.GetJobAsync(jobId);
        finalJob.Should().NotBeNull();
        finalJob!.Status.Should().Be(JobStatus.Completed);
        finalJob.StageDescription.Should().Be("Deals discovered successfully.");
        finalJob.ErrorMessage.Should().BeNull();
        finalJob.Result.Should().BeNull(); // Meal plan result should NOT be generated

        var discoveryResult = finalJob.GetResult<DiscoveryResultDto>();
        discoveryResult.Should().NotBeNull();
        discoveryResult!.Stores.Should().NotBeEmpty();
        discoveryResult.Deals.Should().NotBeEmpty();
        discoveryResult.Deals.Should().AllSatisfy(d => d.StoreId.Should().NotBeNullOrWhiteSpace());

        // Verify status progression: Pending -> DiscoveringStores -> FetchingDeals -> Completed
        var statuses = recordedTransitions.Select(t => t.Status).ToList();
        statuses.Should().ContainInOrder(
            JobStatus.Pending,
            JobStatus.DiscoveringStores,
            JobStatus.FetchingDeals,
            JobStatus.Completed);
        recordedTransitions
            .Where(t => t.Status == JobStatus.FetchingDeals)
            .Select(t => t.StageDescription)
            .Should()
            .Contain("Fetching deals from stores (0/2)")
            .And.Contain("Fetching deals from stores (2/2)");

        // Verify planner was never called
        mockPlanningClient.Verify(p => p.GenerateMealPlanAsync(It.IsAny<GenerateMealPlanRequest>(), It.IsAny<CancellationToken>()), Times.Never);

        // Verify that shopper requests were captured (discovery and deals), but no planner / lookup calls
        mockHandler.CapturedRequests.Should().HaveCount(3);
        mockHandler.CapturedRequests[0].RequestUri!.ToString().Should().Contain("v1/shopper/stores");
        mockHandler.CapturedRequests.Should().Contain(r => r.RequestUri!.ToString().Contains("v1/deals/stores/store_vons_1"));
        mockHandler.CapturedRequests.Should().Contain(r => r.RequestUri!.ToString().Contains("v1/deals/stores/store_grocoutlet_1"));
        mockHandler.CapturedRequests.Should().NotContain(r => r.RequestUri!.ToString().Contains("v1/planner"));
        mockHandler.CapturedRequests.Should().NotContain(r => r.RequestUri!.ToString().Contains("v1/shopper/lookup-ingredients"));
    }

    [Fact]
    public async Task ProcessDiscoveryJobAsync_WhenStoreDealFetchFails_CompletesWithPartialResultsAndReportsFailure()
    {
        var underlyingStore = new InMemoryJobTracker();
        var recordedTransitions = new List<(JobStatus Status, string? StageDescription)>();
        var jobStore = new TrackingJobStateStore(underlyingStore, recordedTransitions.Add);
        var mockHandler = new MockHttpMessageHandler
        {
            CustomHandler = request =>
            {
                if (request.RequestUri?.ToString().Contains("v1/deals/stores/store_vons_1") == true)
                {
                    return new HttpResponseMessage(System.Net.HttpStatusCode.ServiceUnavailable)
                    {
                        Content = new StringContent("Store deals temporarily unavailable")
                    };
                }

                return null;
            }
        };
        var shopperClient = new ShopperClient(
            new HttpClient(mockHandler) { BaseAddress = new Uri("http://localhost:8001/") },
            NullLogger<ShopperClient>.Instance);
        var orchestrator = new MealPlanOrchestrator(
            shopperClient,
            Mock.Of<IPlannerClient>(),
            Mock.Of<IPlanningClient>(),
            jobStore,
            NullLogger<MealPlanOrchestrator>.Instance,
            Mock.Of<IGeocodingService>());
        var jobId = Guid.NewGuid();

        await jobStore.CreateJobAsync(new JobRecord
        {
            JobId = jobId,
            JobType = JobType.StoreDiscovery,
            RequestPayload = new CreateMealPlanRequest
            {
                Address = new AddressDto
                {
                    ZipCode = "90250",
                    Latitude = 33.8958,
                    Longitude = -118.3531
                },
                SearchRadiusMiles = 5
            }
        });

        await orchestrator.ProcessDiscoveryJobAsync(jobId);

        var finalJob = await jobStore.GetJobAsync(jobId);
        finalJob.Should().NotBeNull();
        finalJob!.Status.Should().Be(JobStatus.Completed);
        finalJob.StageDescription.Should().Contain("Partial deal results: 1/2 stores succeeded; 1 failed (store_vons_1).");

        var discoveryResult = finalJob.GetResult<DiscoveryResultDto>();
        discoveryResult.Should().NotBeNull();
        discoveryResult!.Deals.Should().NotBeEmpty();
        discoveryResult.Deals.Should().OnlyContain(deal => deal.StoreId == "store_grocoutlet_1");
        mockHandler.CapturedRequests.Should().Contain(request =>
            request.RequestUri!.ToString().Contains("v1/deals/stores/store_vons_1"));
        mockHandler.CapturedRequests.Should().Contain(request =>
            request.RequestUri!.ToString().Contains("v1/deals/stores/store_grocoutlet_1"));
        recordedTransitions
            .Where(t => t.Status == JobStatus.FetchingDeals)
            .Select(t => t.StageDescription)
            .Should()
            .Contain("Fetching deals from stores (0/2)")
            .And.Contain("Fetching deals from stores (1/2)");
    }

    [Fact]
    public async Task ProcessDiscoveryJobAsync_WhenShopperServiceFails_UpdatesStatusToFailed()
    {
        // Arrange
        var jobStore = new InMemoryJobTracker();
        var mockHandler = new MockHttpMessageHandler();
        mockHandler.SetServerError("Shopper store discovery service unavailable");

        var shopperHttpClient = new HttpClient(mockHandler)
        {
            BaseAddress = new Uri("http://localhost:8001/")
        };
        var shopperClient = new ShopperClient(shopperHttpClient, NullLogger<ShopperClient>.Instance);

        var orchestrator = new MealPlanOrchestrator(
            shopperClient,
            Mock.Of<IPlannerClient>(),
            Mock.Of<IPlanningClient>(),
            jobStore,
            NullLogger<MealPlanOrchestrator>.Instance,
            Mock.Of<IGeocodingService>());

        var jobId = Guid.NewGuid();
        var initialJob = new JobRecord
        {
            JobId = jobId,
            Status = JobStatus.Pending,
            RequestPayload = new CreateMealPlanRequest
            {
                Address = new AddressDto { ZipCode = "90250" }
            }
        };

        await jobStore.CreateJobAsync(initialJob);

        // Act
        await orchestrator.ProcessDiscoveryJobAsync(jobId);

        // Assert
        var finalJob = await jobStore.GetJobAsync(jobId);
        finalJob.Should().NotBeNull();
        finalJob!.Status.Should().Be(JobStatus.Failed);
        finalJob.ErrorMessage.Should().Contain("Shopper store discovery service unavailable");
        finalJob.StageDescription.Should().Be("Deal discovery workflow failed.");
    }

    [Fact]
    public async Task ProcessDiscoveryJobAsync_WhenNoStoresFound_CompletesGracefullyWithoutFetchingDeals()
    {
        // Arrange
        var underlyingStore = new InMemoryJobTracker();
        var recordedTransitions = new List<(JobStatus Status, string? StageDescription)>();

        var jobStore = new TrackingJobStateStore(underlyingStore, transition =>
        {
            recordedTransitions.Add(transition);
        });

        var mockHandler = new MockHttpMessageHandler
        {
            CustomHandler = req =>
            {
                if (req.RequestUri != null && req.RequestUri.ToString().Contains("v1/shopper/stores"))
                {
                    return new HttpResponseMessage(System.Net.HttpStatusCode.OK)
                    {
                        Content = new StringContent("{\"stores\": [], \"total_found\": 0}", System.Text.Encoding.UTF8, "application/json")
                    };
                }
                return null;
            }
        };

        var shopperHttpClient = new HttpClient(mockHandler)
        {
            BaseAddress = new Uri("http://localhost:8001/")
        };
        var shopperClient = new ShopperClient(shopperHttpClient, NullLogger<ShopperClient>.Instance);

        var orchestrator = new MealPlanOrchestrator(
            shopperClient,
            Mock.Of<IPlannerClient>(),
            Mock.Of<IPlanningClient>(),
            jobStore,
            NullLogger<MealPlanOrchestrator>.Instance,
            Mock.Of<IGeocodingService>());

        var jobId = Guid.NewGuid();
        var initialJob = new JobRecord
        {
            JobId = jobId,
            JobType = JobType.StoreDiscovery,
            Status = JobStatus.Pending,
            RequestPayload = new CreateMealPlanRequest
            {
                Address = new AddressDto
                {
                    ZipCode = "90250",
                    Latitude = 33.8958,
                    Longitude = -118.3531
                },
                SearchRadiusMiles = 1
            }
        };

        await jobStore.CreateJobAsync(initialJob);

        // Act
        await orchestrator.ProcessDiscoveryJobAsync(jobId);

        // Assert
        var finalJob = await jobStore.GetJobAsync(jobId);
        finalJob.Should().NotBeNull();
        finalJob!.Status.Should().Be(JobStatus.Completed);
        finalJob.StageDescription.Should().Be("No stores found within search radius.");
        finalJob.ErrorMessage.Should().BeNull();
        finalJob.Result.Should().BeNull();

        // Status transitions should only be Pending -> DiscoveringStores -> Completed (No FetchingDeals)
        var statuses = recordedTransitions.Select(t => t.Status).ToList();
        statuses.Should().ContainInOrder(
            JobStatus.Pending,
            JobStatus.DiscoveringStores,
            JobStatus.Completed);
        statuses.Should().NotContain(JobStatus.FetchingDeals);

        // Verify that only the store discovery request was made, no deal fetching calls
        mockHandler.CapturedRequests.Should().HaveCount(1);
        mockHandler.CapturedRequests[0].RequestUri!.ToString().Should().Contain("v1/shopper/stores");
        mockHandler.CapturedRequests.Should().NotContain(r => r.RequestUri!.ToString().Contains("v1/deals"));
    }

    #endregion

    #region ProcessGenerationJobAsync Tests

    [Fact]
    public async Task ProcessGenerationJobAsync_PopulatesTopDealsViaBatchLookupAndCompletes()
    {
        // Arrange
        var underlyingStore = new InMemoryJobTracker();
        var recordedTransitions = new List<(JobStatus Status, string? StageDescription)>();

        var jobStore = new TrackingJobStateStore(underlyingStore, transition =>
        {
            recordedTransitions.Add(transition);
        });

        var mockHandler = new MockHttpMessageHandler();

        var shopperHttpClient = new HttpClient(mockHandler)
        {
            BaseAddress = new Uri("http://localhost:8001/")
        };
        var shopperClient = new ShopperClient(shopperHttpClient, NullLogger<ShopperClient>.Instance);

        var plannerHttpClient = new HttpClient(mockHandler)
        {
            BaseAddress = new Uri("http://localhost:8002/")
        };
        var planningClient = new PlanningClient(plannerHttpClient, NullLogger<PlanningClient>.Instance);

        var orchestrator = new MealPlanOrchestrator(
            shopperClient,
            Mock.Of<IPlannerClient>(),
            planningClient,
            jobStore,
            NullLogger<MealPlanOrchestrator>.Instance,
            Mock.Of<IGeocodingService>());

        var jobId = Guid.NewGuid();
        var genRequest = new MealPlanGenerationRequest
        {
            SelectedStoreIds = ["store-ralphs-101", "store-sprouts-305"],
            SelectedDealIds =
            [
                "store-ralphs-101_deal-chicken-breast-001",
                "store-sprouts-305_deal-bell-peppers-002"
            ],
            Cuisines = ["Southern", "Classic American", "Comfort Food"],
            DietaryPreferences = ["Keto"],
            AvoidIngredients = ["onions", "corn", "mango"],
            DaysCount = 3,
            ServingsCount = 4
        };

        var initialJob = new JobRecord
        {
            JobId = jobId,
            JobType = JobType.PlanGeneration,
            Status = JobStatus.Pending,
            RequestPayloadJson = System.Text.Json.JsonSerializer.Serialize(genRequest)
        };

        await jobStore.CreateJobAsync(initialJob);

        // Act
        await orchestrator.ProcessGenerationJobAsync(jobId);

        // Assert
        var finalJob = await jobStore.GetJobAsync(jobId);
        finalJob.Should().NotBeNull();
        finalJob!.Status.Should().Be(JobStatus.Completed);
        finalJob.ErrorMessage.Should().BeNull();
        finalJob.Result.Should().NotBeNull();
        finalJob.Result!.Recipes.Should().NotBeEmpty();

        // Verify batch lookup was called and planner received top deals
        var batchLookupRequest = mockHandler.CapturedRequests.Single(
            request => request.RequestUri!.ToString().Contains("v1/shopper/deals/batch-lookup"));
        var batchLookupBody = await batchLookupRequest.Content!.ReadAsStringAsync();
        using var batchLookupJson = System.Text.Json.JsonDocument.Parse(batchLookupBody);
        var lookupItems = batchLookupJson.RootElement.GetProperty("items").EnumerateArray().ToList();
        lookupItems.Should().HaveCount(2);
        lookupItems[0].GetProperty("deal_id").GetString().Should().Be("deal-chicken-breast-001");
        lookupItems[0].GetProperty("store_id").GetString().Should().Be("store-ralphs-101");
        lookupItems[1].GetProperty("deal_id").GetString().Should().Be("deal-bell-peppers-002");
        lookupItems[1].GetProperty("store_id").GetString().Should().Be("store-sprouts-305");

        var plannerRequest = mockHandler.CapturedRequests.Single(
            request => request.RequestUri!.ToString().Contains("v1/planner/generate"));
        var plannerBody = await plannerRequest.Content!.ReadAsStringAsync();
        using var plannerJson = System.Text.Json.JsonDocument.Parse(plannerBody);
        var plannerRoot = plannerJson.RootElement;
        plannerRoot.GetProperty("cuisines").EnumerateArray().Select(item => item.GetString())
            .Should().BeEquivalentTo(["Southern", "Classic American", "Comfort Food"]);
        plannerRoot.GetProperty("dietary_restrictions").EnumerateArray().Select(item => item.GetString())
            .Should().ContainSingle().Which.Should().Be("Keto");
        plannerRoot.GetProperty("avoid_ingredients").EnumerateArray().Select(item => item.GetString())
            .Should().BeEquivalentTo(["onions", "corn", "mango"]);
        plannerRoot.GetProperty("days_count").GetInt32().Should().Be(3);
        plannerRoot.GetProperty("household_size").GetInt32().Should().Be(4);
        var plannerDeals = plannerRoot.GetProperty("top_deals").EnumerateArray().ToList();
        plannerDeals.Should().HaveCount(2);
        plannerDeals[0].GetProperty("deal_id").GetString().Should().Be("deal-chicken-breast-001");
        plannerDeals[0].GetProperty("primary_ingredient").GetString().Should().Be("Chicken Breast");

        finalJob.Result!.Recipes[0].IngredientsWithDeals
            .Should().Contain(ingredient =>
                ingredient.Name == "Boneless Skinless Chicken Breast" &&
                ingredient.IsPromotional &&
                ingredient.StoreName == "Ralphs" &&
                ingredient.DealPriceDescription == "$2.99 / lb");
    }

    [Theory]
    [InlineData(true)]
    [InlineData(false)]
    public async Task ProcessGenerationJobAsync_UsesSourceStoreIdEmbeddedInSelectedDealId(
        bool selectedDealIdIncludesSelectedStorePrefix)
    {
        var jobStore = new InMemoryJobTracker();
        var mockHandler = new MockHttpMessageHandler();
        const string selectedStoreId = "vons-5673941";
        const string sourceStoreId = "vons-5605136";
        var rawDealIds = new[]
        {
            $"{sourceStoreId}_1046379157_1",
            $"{sourceStoreId}_1046379154",
            $"{sourceStoreId}_1046379158"
        };
        mockHandler.CustomHandler = request =>
            request.RequestUri!.ToString().Contains("v1/shopper/deals/batch-lookup")
                ? new System.Net.Http.HttpResponseMessage(System.Net.HttpStatusCode.OK)
                {
                    Content = new System.Net.Http.StringContent(
                        $$"""
                        {
                          "deals": [
                            {
                              "deal_id": "{{rawDealIds[0]}}",
                              "store_id": "{{sourceStoreId}}",
                              "store_name": "Vons",
                              "item_name": "Chicken Breast",
                              "category": "Meat & Poultry",
                              "price": 2.99,
                              "unit": "lb",
                              "discount_percentage": 20,
                              "primary_ingredient": "Chicken Breast"
                            },
                            {
                              "deal_id": "{{rawDealIds[1]}}",
                              "store_id": "{{sourceStoreId}}",
                              "store_name": "Vons",
                              "item_name": "Ground Beef",
                              "category": "Meat & Poultry",
                              "price": 3.99,
                              "unit": "lb",
                              "discount_percentage": 20,
                              "primary_ingredient": "Ground Beef"
                            },
                            {
                              "deal_id": "{{rawDealIds[2]}}",
                              "store_id": "{{sourceStoreId}}",
                              "store_name": "Vons",
                              "item_name": "Pork Chops",
                              "category": "Meat & Poultry",
                              "price": 2.49,
                              "unit": "lb",
                              "discount_percentage": 20,
                              "primary_ingredient": "Pork Chops"
                            }
                          ],
                          "total_found": 3
                        }
                        """,
                        System.Text.Encoding.UTF8,
                        "application/json")
                }
                : null;
        var shopperClient = new ShopperClient(
            new HttpClient(mockHandler) { BaseAddress = new Uri("http://localhost:8001/") },
            NullLogger<ShopperClient>.Instance);
        var planningClient = new PlanningClient(
            new HttpClient(mockHandler) { BaseAddress = new Uri("http://localhost:8002/") },
            NullLogger<PlanningClient>.Instance);
        var orchestrator = new MealPlanOrchestrator(
            shopperClient,
            Mock.Of<IPlannerClient>(),
            planningClient,
            jobStore,
            NullLogger<MealPlanOrchestrator>.Instance,
            Mock.Of<IGeocodingService>());

        var jobId = Guid.NewGuid();
        await jobStore.CreateJobAsync(new JobRecord
        {
            JobId = jobId,
            JobType = JobType.PlanGeneration,
            Status = JobStatus.Pending,
            RequestPayloadJson = System.Text.Json.JsonSerializer.Serialize(new MealPlanGenerationRequest
            {
                SelectedStoreIds = [selectedStoreId],
                SelectedDealIds = selectedDealIdIncludesSelectedStorePrefix
                    ? rawDealIds.Select(rawDealId => $"{selectedStoreId}_{rawDealId}").ToList()
                    : rawDealIds.ToList()
            })
        });

        await orchestrator.ProcessGenerationJobAsync(jobId);

        (await jobStore.GetJobAsync(jobId))!.Status.Should().Be(JobStatus.Completed);
        var lookupRequest = mockHandler.CapturedRequests.Single(
            request => request.RequestUri!.ToString().Contains("v1/shopper/deals/batch-lookup"));
        var requestBody = await lookupRequest.Content!.ReadAsStringAsync();
        using var requestJson = System.Text.Json.JsonDocument.Parse(requestBody);
        var lookups = requestJson.RootElement.GetProperty("items").EnumerateArray().ToList();
        lookups.Should().HaveCount(3);
        for (var index = 0; index < rawDealIds.Length; index++)
        {
            lookups[index].GetProperty("deal_id").GetString().Should().Be(rawDealIds[index]);
            lookups[index].GetProperty("store_id").GetString().Should().Be(sourceStoreId);
        }
    }

    #endregion
}
