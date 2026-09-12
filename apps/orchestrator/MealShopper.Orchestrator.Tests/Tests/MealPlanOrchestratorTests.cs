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
        finalJob!.Status.Should().Be(JobStatus.GeneratingMealPlan);
        finalJob.StageDescription.Should().Be("Synthesizing customized recipes from curated deals...");
        finalJob.ErrorMessage.Should().BeNull();

        // Verify status progression: Pending -> DiscoveringStores -> FetchingDeals -> GeneratingMealPlan
        var statuses = recordedTransitions.Select(t => t.Status).ToList();
        statuses.Should().Equal(
            JobStatus.Pending,
            JobStatus.DiscoveringStores,
            JobStatus.FetchingDeals,
            JobStatus.GeneratingMealPlan);

        // Verify that stores, deals, and planner requests were captured
        mockHandler.CapturedRequests.Should().HaveCount(3);
        mockHandler.CapturedRequests[0].RequestUri!.ToString().Should().Contain("v1/shopper/stores");
        mockHandler.CapturedRequests[1].RequestUri!.ToString().Should().Contain("v1/shopper/deals");
        mockHandler.CapturedRequests[2].RequestUri!.ToString().Should().Contain("v1/planner/generate");
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
}
