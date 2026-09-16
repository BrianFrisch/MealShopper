using FluentAssertions;
using MealShopper.Orchestrator.Clients;
using MealShopper.Orchestrator.Models;
using MealShopper.Orchestrator.Models.DTOs;
using MealShopper.Orchestrator.Services;
using MealShopper.Orchestrator.Tests.Helpers;
using Microsoft.Extensions.Logging.Abstractions;

namespace MealShopper.Orchestrator.Tests.Tests;

public class MealPlanOrchestratorTests
{
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
            jobStore,
            shopperClient,
            planningClient,
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
            jobStore,
            shopperClient,
            planningClient,
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
            jobStore,
            shopperClient,
            planningClient,
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
            jobStore,
            shopperClient,
            planningClient,
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
        chickenRecipe.IngredientsWithDeals.Should().Contain(i => i.Name == "Olive Oil" && i.StoreName == "Grocery Outlet" && i.DealPriceDescription == "$5.99 / tbsp");
        chickenRecipe.IngredientsWithDeals.Should().Contain(i => i.Name == "Boneless Skinless Chicken Breast" && i.StoreName == "Ralphs");
        chickenRecipe.PantryIngredients.Should().Contain(i => i.Name == "Lemon Pepper Seasoning" && i.StoreName == null && i.DealPriceDescription == null);

        // Second recipe: Street Tacos (Ground Beef was missing and loop-back matched with Vons)
        var tacosRecipe = result.Recipes.First(r => r.RecipeTitle == "Street Tacos");
        tacosRecipe.IngredientsWithDeals.Should().Contain(i => i.Name == "Ground Beef (85/15)" && i.StoreName == "Vons" && i.DealPriceDescription == "$4.99 / lbs");
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
            jobStore,
            shopperClient,
            planningClient,
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

            // Deals ingredients must have valid store and price info
            recipe.IngredientsWithDeals.Should().NotBeEmpty();
            foreach (var dealIngredient in recipe.IngredientsWithDeals)
            {
                dealIngredient.Name.Should().NotBeNullOrWhiteSpace();
                dealIngredient.AmountDescription.Should().NotBeNullOrWhiteSpace();
                dealIngredient.StoreName.Should().NotBeNullOrWhiteSpace();
                dealIngredient.DealPriceDescription.Should().StartWith("$");
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
