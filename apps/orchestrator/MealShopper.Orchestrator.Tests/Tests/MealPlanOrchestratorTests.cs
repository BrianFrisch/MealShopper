using FluentAssertions;
using MealShopper.Orchestrator.Clients;
using MealShopper.Orchestrator.Exceptions;
using MealShopper.Orchestrator.Models;
using MealShopper.Orchestrator.Models.Domain;
using MealShopper.Orchestrator.Models.DTOs;
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
            NullLogger<MealPlanOrchestrator>.Instance);

        var request = new PlanGenerationWorkflowRequest(
            Latitude: 34.0522,
            Longitude: -118.2437,
            RadiusMiles: 5.0,
            MaxStores: 2,
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

        mockShopper.Verify(s => s.DiscoverStoresAsync(It.Is<StoreDiscoveryRequest>(r => r.Latitude == 34.0522 && r.MaxStores == 2), It.IsAny<CancellationToken>()), Times.Once);
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
            NullLogger<MealPlanOrchestrator>.Instance);

        var request = new PlanGenerationWorkflowRequest(
            Latitude: 34.0522,
            Longitude: -118.2437,
            RadiusMiles: 2.0,
            MaxStores: 2,
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
            NullLogger<MealPlanOrchestrator>.Instance);

        var request = new PlanGenerationWorkflowRequest(
            Latitude: 34.0,
            Longitude: -118.0,
            RadiusMiles: 5.0,
            MaxStores: 1,
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
            NullLogger<MealPlanOrchestrator>.Instance);

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
                SearchRadiusMiles = 5,
                MaxStores = 2
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

        // Verify that stores, deals, planner, and loopback lookup requests were captured
        mockHandler.CapturedRequests.Should().HaveCount(4);
        mockHandler.CapturedRequests[0].RequestUri!.ToString().Should().Contain("v1/shopper/stores");
        mockHandler.CapturedRequests[1].RequestUri!.ToString().Should().Contain("v1/shopper/deals");
        mockHandler.CapturedRequests[2].RequestUri!.ToString().Should().Contain("v1/planner/generate");
        mockHandler.CapturedRequests[3].RequestUri!.ToString().Should().Contain("v1/shopper/lookup-ingredients");
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

        public async Task<JobRecord?> CompleteJobAsync(
            Guid jobId,
            MealPlanResultDto result,
            CancellationToken cancellationToken = default)
        {
            _onStatusRecorded((JobStatus.Completed, "Meal plan generated successfully."));
            return await _inner.CompleteJobAsync(jobId, result, cancellationToken);
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
            NullLogger<MealPlanOrchestrator>.Instance);

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
            NullLogger<MealPlanOrchestrator>.Instance);

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
            NullLogger<MealPlanOrchestrator>.Instance);

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
            NullLogger<MealPlanOrchestrator>.Instance);

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
                SearchRadiusMiles = 5,
                MaxStores = 2
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
}
