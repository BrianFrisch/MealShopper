using System.Text.Json;
using FluentAssertions;
using MealShopper.Common.Security;
using MealShopper.Orchestrator.Controllers;
using MealShopper.Orchestrator.Models;
using MealShopper.Orchestrator.Models.DTOs;
using MealShopper.Orchestrator.Services;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Logging.Abstractions;
using Moq;
using Xunit;

namespace MealShopper.Orchestrator.Tests.Tests;

public class MealPlansControllerTests
{
    private readonly Mock<IJobStateStore> _mockJobStore;
    private readonly Mock<IMealPlanOrchestrator> _mockOrchestrator;
    private readonly Mock<IGatewayUserContext> _mockUserContext;
    private readonly MealPlansController _controller;

    public MealPlansControllerTests()
    {
        _mockJobStore = new Mock<IJobStateStore>();
        _mockOrchestrator = new Mock<IMealPlanOrchestrator>();
        _mockUserContext = new Mock<IGatewayUserContext>();

        _mockUserContext.Setup(u => u.UserId).Returns(Guid.NewGuid());
        _mockUserContext.Setup(u => u.Roles).Returns(new[] { "User" });

        _controller = new MealPlansController(
            _mockJobStore.Object,
            _mockOrchestrator.Object,
            NullLogger<MealPlansController>.Instance,
            _mockUserContext.Object)
        {
            ControllerContext = new ControllerContext
            {
                HttpContext = new DefaultHttpContext()
            }
        };
    }

    [Fact]
    public async Task DiscoverDeals_WhenModelStateIsInvalid_ReturnsBadRequest()
    {
        // Arrange
        _controller.ModelState.AddModelError("Address.ZipCode", "ZipCode is required.");
        var request = new MealPlanDiscoveryRequest();

        // Act
        var result = await _controller.DiscoverDeals(request, CancellationToken.None);

        // Assert
        result.Should().BeOfType<BadRequestObjectResult>();
        _mockJobStore.Verify(s => s.CreateJobAsync(It.IsAny<JobRecord>(), It.IsAny<CancellationToken>()), Times.Never);
    }

    [Fact]
    public async Task DiscoverDeals_WhenValidRequest_CreatesJobAndReturnsAccepted()
    {
        // Arrange
        var request = new MealPlanDiscoveryRequest
        {
            Address = new AddressDto
            {
                ZipCode = "90250",
                Latitude = 33.8958,
                Longitude = -118.3531
            },
            SearchRadiusMiles = 5
        };

        JobRecord? savedJob = null;
        _mockJobStore
            .Setup(s => s.CreateJobAsync(It.IsAny<JobRecord>(), It.IsAny<CancellationToken>()))
            .Callback<JobRecord, CancellationToken>((job, _) => savedJob = job)
            .ReturnsAsync((JobRecord job, CancellationToken _) => job);

        // Act
        var result = await _controller.DiscoverDeals(request, CancellationToken.None);

        // Assert
        var acceptedResult = result.Should().BeOfType<AcceptedResult>().Subject;
        acceptedResult.Value.Should().BeOfType<CreateMealPlanResponse>();

        var response = (CreateMealPlanResponse)acceptedResult.Value!;
        response.JobId.Should().NotBeEmpty();
        response.Status.Should().Be("Pending");

        acceptedResult.Location.Should().Be($"/v1/tasks/{response.JobId}");
        _controller.Response.Headers.Location.ToString().Should().Be($"/v1/tasks/{response.JobId}");

        savedJob.Should().NotBeNull();
        savedJob!.JobId.Should().Be(response.JobId);
        savedJob.Status.Should().Be(JobStatus.Pending);
        savedJob.RequestPayload.Address.ZipCode.Should().Be("90250");
        savedJob.RequestPayload.SearchRadiusMiles.Should().Be(5);
    }

    [Fact]
    public async Task GenerateMealPlanFromDeals_WhenValidRequest_PersistsAuthenticatedUserIdOnJob()
    {
        JobRecord? savedJob = null;
        _mockJobStore
            .Setup(store => store.CreateJobAsync(It.IsAny<JobRecord>(), It.IsAny<CancellationToken>()))
            .Callback<JobRecord, CancellationToken>((job, _) => savedJob = job)
            .ReturnsAsync((JobRecord job, CancellationToken _) => job);

        var result = await _controller.GenerateMealPlanFromDeals(
            new MealPlanGenerationRequest
            {
                SelectedStoreIds = ["store-1"],
                SelectedDealIds = ["deal-1"]
            },
            CancellationToken.None);

        result.Should().BeOfType<AcceptedResult>();
        savedJob.Should().NotBeNull();
        savedJob!.UserId.Should().Be(_mockUserContext.Object.UserId);
        savedJob.JobType.Should().Be(JobType.PlanGeneration);
    }

    [Fact]
    public async Task CreateMealPlan_WhenValidRequest_PersistsAuthenticatedUserIdOnJob()
    {
        JobRecord? savedJob = null;
        _mockJobStore
            .Setup(store => store.CreateJobAsync(It.IsAny<JobRecord>(), It.IsAny<CancellationToken>()))
            .Callback<JobRecord, CancellationToken>((job, _) => savedJob = job)
            .ReturnsAsync((JobRecord job, CancellationToken _) => job);

        var result = await _controller.CreateMealPlan(
            new CreateMealPlanRequest
            {
                Address = new AddressDto
                {
                    ZipCode = "90250",
                    Latitude = 33.8958,
                    Longitude = -118.3531
                },
                SearchRadiusMiles = 5
            },
            CancellationToken.None);

        result.Should().BeOfType<AcceptedResult>();
        savedJob.Should().NotBeNull();
        savedJob!.UserId.Should().Be(_mockUserContext.Object.UserId);
    }

    [Fact]
    public async Task ConfirmMealPlan_WhenValidSelection_SavesKeptRecipes()
    {
        var jobId = Guid.NewGuid();
        var mealPlan = new MealPlanResultDto
        {
            MealPlanId = "meal-plan-1",
            Recipes =
            [
                new RecipeCardDto { RecipeId = "recipe-1" },
                new RecipeCardDto { RecipeId = "recipe-2" }
            ]
        };
        var job = new JobRecord
        {
            JobId = jobId,
            JobType = JobType.PlanGeneration,
            Status = JobStatus.Completed,
            ResultPayloadJson = JsonSerializer.Serialize(mealPlan)
        };
        MealPlanResultDto? savedResult = null;

        _mockJobStore.Setup(store => store.GetJobAsync(jobId, It.IsAny<CancellationToken>()))
            .ReturnsAsync(job);
        _mockJobStore.Setup(store => store.CompleteJobAsync(
                jobId,
                It.IsAny<MealPlanResultDto>(),
                "Meal plan saved successfully.",
                It.IsAny<CancellationToken>()))
            .Callback<Guid, MealPlanResultDto, string?, CancellationToken>((_, result, _, _) => savedResult = result)
            .ReturnsAsync(job);

        var response = await _controller.ConfirmMealPlan(
            jobId,
            new ConfirmMealPlanRequest { SelectedRecipeIds = ["recipe-1"] },
            CancellationToken.None);

        response.Should().BeOfType<OkObjectResult>();
        savedResult.Should().NotBeNull();
        savedResult!.Recipes.Single(recipe => recipe.RecipeId == "recipe-1").IsKept.Should().BeTrue();
        savedResult.Recipes.Single(recipe => recipe.RecipeId == "recipe-2").IsKept.Should().BeFalse();
    }

    [Fact]
    public async Task ConfirmMealPlan_WhenRecipeDoesNotBelongToPlan_ReturnsBadRequest()
    {
        var jobId = Guid.NewGuid();
        var mealPlan = new MealPlanResultDto
        {
            MealPlanId = "meal-plan-1",
            Recipes = [new RecipeCardDto { RecipeId = "recipe-1" }]
        };
        var job = new JobRecord
        {
            JobId = jobId,
            JobType = JobType.PlanGeneration,
            Status = JobStatus.Completed,
            ResultPayloadJson = JsonSerializer.Serialize(mealPlan)
        };
        _mockJobStore.Setup(store => store.GetJobAsync(jobId, It.IsAny<CancellationToken>()))
            .ReturnsAsync(job);

        var response = await _controller.ConfirmMealPlan(
            jobId,
            new ConfirmMealPlanRequest { SelectedRecipeIds = ["unknown-recipe"] },
            CancellationToken.None);

        response.Should().BeOfType<BadRequestObjectResult>();
        _mockJobStore.Verify(
            store => store.CompleteJobAsync(
                It.IsAny<Guid>(),
                It.IsAny<MealPlanResultDto>(),
                It.IsAny<string>(),
                It.IsAny<CancellationToken>()),
            Times.Never);
    }
}
