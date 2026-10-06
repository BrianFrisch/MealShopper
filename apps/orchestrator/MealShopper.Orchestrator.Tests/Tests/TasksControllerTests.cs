using System.Text.Json;
using FluentAssertions;
using MealShopper.Orchestrator.Controllers;
using MealShopper.Orchestrator.Models;
using MealShopper.Orchestrator.Models.Domain;
using MealShopper.Orchestrator.Models.DTOs;
using MealShopper.Orchestrator.Models.Shopper;
using MealShopper.Orchestrator.Services;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Logging.Abstractions;
using Moq;
using Xunit;

namespace MealShopper.Orchestrator.Tests.Tests;

public class TasksControllerTests
{
    private readonly Mock<IJobStateStore> _mockJobStore;
    private readonly TasksController _controller;

    public TasksControllerTests()
    {
        _mockJobStore = new Mock<IJobStateStore>();
        _controller = new TasksController(_mockJobStore.Object, NullLogger<TasksController>.Instance);
    }

    [Fact]
    public async Task GetTaskStatus_WhenTaskNotFound_ReturnsNotFound()
    {
        // Arrange
        var taskId = Guid.NewGuid();
        _mockJobStore.Setup(s => s.GetJobAsync(taskId, It.IsAny<CancellationToken>()))
            .ReturnsAsync((JobRecord?)null);

        // Act
        var result = await _controller.GetTaskStatus(taskId, CancellationToken.None);

        // Assert
        result.Should().BeOfType<NotFoundObjectResult>();
    }

    [Fact]
    public async Task GetTaskStatus_WhenDiscoveryJobCompleted_ReturnsDiscoveryResultInPayload()
    {
        // Arrange
        var taskId = Guid.NewGuid();
        var discoveryResult = new DiscoveryResultDto
        {
            Stores = new List<StoreDto>
            {
                new() { Id = "store-vons", Name = "Vons", ZipCode = "90260" }
            },
            Deals = new List<DealItemDto>
            {
                new() { DealId = "deal-1", StoreId = "store-vons", StoreName = "Vons", ItemName = "Chicken Breast", DealPrice = 2.99m }
            }
        };

        var job = new JobRecord
        {
            JobId = taskId,
            JobType = JobType.StoreDiscovery,
            Status = JobStatus.Completed,
            StageDescription = "Deals discovered successfully.",
            ResultPayloadJson = JsonSerializer.Serialize(discoveryResult)
        };

        _mockJobStore.Setup(s => s.GetJobAsync(taskId, It.IsAny<CancellationToken>()))
            .ReturnsAsync(job);

        // Act
        var result = await _controller.GetTaskStatus(taskId, CancellationToken.None);

        // Assert
        var okResult = result.Should().BeOfType<OkObjectResult>().Subject;
        var json = JsonSerializer.Serialize(okResult.Value);
        using var doc = JsonDocument.Parse(json);
        var root = doc.RootElement;

        root.GetProperty("jobId").GetString().Should().Be(taskId.ToString());
        root.GetProperty("status").GetString().Should().Be("Completed");
        root.GetProperty("stageDescription").GetString().Should().Be("Deals discovered successfully.");

        var resultObj = root.GetProperty("result");
        resultObj.GetProperty("stores").GetArrayLength().Should().Be(1);
        resultObj.GetProperty("stores")[0].GetProperty("id").GetString().Should().Be("store-vons");
        resultObj.GetProperty("deals").GetArrayLength().Should().Be(1);
        resultObj.GetProperty("deals")[0].GetProperty("store_id").GetString().Should().Be("store-vons");
        resultObj.GetProperty("deals")[0].GetProperty("item_name").GetString().Should().Be("Chicken Breast");
    }
}
