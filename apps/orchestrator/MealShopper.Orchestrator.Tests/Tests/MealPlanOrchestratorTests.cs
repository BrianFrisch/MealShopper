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
        var jobStore = new InMemoryJobTracker();
        var mockHandler = new MockHttpMessageHandler();
        var httpClient = new HttpClient(mockHandler)
        {
            BaseAddress = new Uri("http://localhost:8001/")
        };
        var shopperClient = new ShopperClient(httpClient, NullLogger<ShopperClient>.Instance);
        var orchestrator = new MealPlanOrchestrator(
            jobStore,
            shopperClient,
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

        var recordedStatuses = new List<(JobStatus Status, string? StageDescription)>();

        // Act
        await orchestrator.ProcessJobAsync(jobId);

        // Assert
        var finalJob = await jobStore.GetJobAsync(jobId);
        finalJob.Should().NotBeNull();
        finalJob!.Status.Should().Be(JobStatus.FetchingDeals);
        finalJob.StageDescription.Should().Be("Fetching circulars and scoring top promotional deals...");
        finalJob.ErrorMessage.Should().BeNull();

        // Verify that stores and deals requests were actually captured by the mock handler
        mockHandler.CapturedRequests.Should().HaveCount(2);
        mockHandler.CapturedRequests[0].RequestUri!.ToString().Should().Contain("v1/shopper/stores");
        mockHandler.CapturedRequests[1].RequestUri!.ToString().Should().Contain("v1/shopper/deals");
    }

    [Fact]
    public async Task ProcessJobAsync_WhenShopperServiceFails_UpdatesStatusToFailed()
    {
        // Arrange
        var jobStore = new InMemoryJobTracker();
        var mockHandler = new MockHttpMessageHandler();
        mockHandler.SetServerError("Shopper store discovery service unavailable");

        var httpClient = new HttpClient(mockHandler)
        {
            BaseAddress = new Uri("http://localhost:8001/")
        };
        var shopperClient = new ShopperClient(httpClient, NullLogger<ShopperClient>.Instance);
        var orchestrator = new MealPlanOrchestrator(
            jobStore,
            shopperClient,
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
}
