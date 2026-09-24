using System.Text.Json;
using FluentAssertions;
using MealShopper.Orchestrator.Exceptions;
using MealShopper.Orchestrator.Models;
using MealShopper.Orchestrator.Models.DTOs;
using MealShopper.Orchestrator.Services;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;
using Moq;
using StackExchange.Redis;
using Xunit;

namespace MealShopper.Orchestrator.Tests.Tests;

public class RedisJobStateStoreTests
{
    private readonly Mock<IConnectionMultiplexer> _redisMock;
    private readonly Mock<IDatabase> _dbMock;
    private readonly Mock<ILogger<RedisJobStateStore>> _loggerMock;
    private readonly IConfiguration _config;

    public RedisJobStateStoreTests()
    {
        _redisMock = new Mock<IConnectionMultiplexer>();
        _dbMock = new Mock<IDatabase>();
        _loggerMock = new Mock<ILogger<RedisJobStateStore>>();

        _redisMock.Setup(r => r.GetDatabase(It.IsAny<int>(), It.IsAny<object>()))
            .Returns(_dbMock.Object);

        var inMemorySettings = new Dictionary<string, string?>
        {
            { "Redis:InstanceName", "mealshopper:jobs:" }
        };

        _config = new ConfigurationBuilder()
            .AddInMemoryCollection(inMemorySettings)
            .Build();
    }

    [Fact]
    public void Constructor_NullRedis_ThrowsArgumentNullException()
    {
        var act = () => new RedisJobStateStore(null!, _config, _loggerMock.Object);
        act.Should().Throw<ArgumentNullException>();
    }

    [Fact]
    public void Constructor_NullConfig_ThrowsArgumentNullException()
    {
        var act = () => new RedisJobStateStore(_redisMock.Object, null!, _loggerMock.Object);
        act.Should().Throw<ArgumentNullException>();
    }

    [Fact]
    public void Constructor_NullLogger_ThrowsArgumentNullException()
    {
        var act = () => new RedisJobStateStore(_redisMock.Object, _config, null!);
        act.Should().Throw<ArgumentNullException>();
    }

    [Fact]
    public async Task CreateJobAsync_WithJobRecord_SavesToRedisWith24HourExpiry()
    {
        // Arrange
        var store = new RedisJobStateStore(_redisMock.Object, _config, _loggerMock.Object);
        var job = new JobRecord
        {
            JobId = Guid.NewGuid(),
            Status = JobStatus.Pending,
            CreatedAt = DateTimeOffset.UtcNow,
            UpdatedAt = DateTimeOffset.UtcNow
        };

        _dbMock.Setup(db => db.StringSetAsync(
            (RedisKey)$"mealshopper:jobs:{job.JobId}",
            It.IsAny<RedisValue>(),
            TimeSpan.FromHours(24),
            It.IsAny<bool>(),
            It.IsAny<When>(),
            It.IsAny<CommandFlags>()))
            .ReturnsAsync(true);

        // Act
        var result = await store.CreateJobAsync(job);

        // Assert
        result.Should().BeEquivalentTo(job);
        _dbMock.Verify(db => db.StringSetAsync(
            (RedisKey)$"mealshopper:jobs:{job.JobId}",
            It.Is<RedisValue>(v => v.ToString().Contains(job.JobId.ToString())),
            TimeSpan.FromHours(24),
            It.IsAny<bool>(),
            It.IsAny<When>(),
            It.IsAny<CommandFlags>()), Times.Once);
    }

    [Fact]
    public async Task CreateJobAsync_WithPayload_CreatesPendingJobAndSavesToRedis()
    {
        // Arrange
        var store = new RedisJobStateStore(_redisMock.Object, _config, _loggerMock.Object);
        var payload = new CreateMealPlanRequest
        {
            Cuisines = new List<string> { "Italian" },
            SearchRadiusMiles = 5,
            MaxStores = 2
        };

        _dbMock.Setup(db => db.StringSetAsync(
            It.IsAny<RedisKey>(),
            It.IsAny<RedisValue>(),
            TimeSpan.FromHours(24),
            It.IsAny<bool>(),
            It.IsAny<When>(),
            It.IsAny<CommandFlags>()))
            .ReturnsAsync(true);

        // Act
        var result = await store.CreateJobAsync(payload);

        // Assert
        result.Should().NotBeNull();
        result.Status.Should().Be(JobStatus.Pending);
        result.RequestPayload.Cuisines.Should().Contain("Italian");
        _dbMock.Verify(db => db.StringSetAsync(
            (RedisKey)$"mealshopper:jobs:{result.JobId}",
            It.IsAny<RedisValue>(),
            TimeSpan.FromHours(24),
            It.IsAny<bool>(),
            It.IsAny<When>(),
            It.IsAny<CommandFlags>()), Times.Once);
    }

    [Fact]
    public async Task GetJobAsync_WhenKeyExists_ReturnsDeserializedJobRecord()
    {
        // Arrange
        var store = new RedisJobStateStore(_redisMock.Object, _config, _loggerMock.Object);
        var jobId = Guid.NewGuid();
        var job = new JobRecord
        {
            JobId = jobId,
            Status = JobStatus.DiscoveringStores,
            StageDescription = "Searching for nearby stores...",
            CreatedAt = DateTimeOffset.UtcNow,
            UpdatedAt = DateTimeOffset.UtcNow
        };

        var json = JsonSerializer.Serialize(job, new JsonSerializerOptions { PropertyNamingPolicy = JsonNamingPolicy.CamelCase });

        _dbMock.Setup(db => db.StringGetAsync((RedisKey)$"mealshopper:jobs:{jobId}", It.IsAny<CommandFlags>()))
            .ReturnsAsync((RedisValue)json);

        // Act
        var result = await store.GetJobAsync(jobId);

        // Assert
        result.Should().NotBeNull();
        result!.JobId.Should().Be(jobId);
        result.Status.Should().Be(JobStatus.DiscoveringStores);
        result.StageDescription.Should().Be("Searching for nearby stores...");
    }

    [Fact]
    public async Task GetJobAsync_WhenKeyDoesNotExist_ReturnsNull()
    {
        // Arrange
        var store = new RedisJobStateStore(_redisMock.Object, _config, _loggerMock.Object);
        var jobId = Guid.NewGuid();

        _dbMock.Setup(db => db.StringGetAsync((RedisKey)$"mealshopper:jobs:{jobId}", It.IsAny<CommandFlags>()))
            .ReturnsAsync(RedisValue.Null);

        // Act
        var result = await store.GetJobAsync(jobId);

        // Assert
        result.Should().BeNull();
    }

    [Fact]
    public async Task UpdateJobStatusAsync_WhenKeyExists_UpdatesStatusAndRefreshesTTL()
    {
        // Arrange
        var store = new RedisJobStateStore(_redisMock.Object, _config, _loggerMock.Object);
        var jobId = Guid.NewGuid();
        var initialCreatedAt = DateTimeOffset.UtcNow.AddMinutes(-5);
        var initialJob = new JobRecord
        {
            JobId = jobId,
            Status = JobStatus.Pending,
            CreatedAt = initialCreatedAt,
            UpdatedAt = initialCreatedAt
        };

        var initialJson = JsonSerializer.Serialize(initialJob, new JsonSerializerOptions { PropertyNamingPolicy = JsonNamingPolicy.CamelCase });

        _dbMock.Setup(db => db.StringGetAsync((RedisKey)$"mealshopper:jobs:{jobId}", It.IsAny<CommandFlags>()))
            .ReturnsAsync((RedisValue)initialJson);

        _dbMock.Setup(db => db.StringSetAsync(
            (RedisKey)$"mealshopper:jobs:{jobId}",
            It.IsAny<RedisValue>(),
            TimeSpan.FromHours(24),
            It.IsAny<bool>(),
            It.IsAny<When>(),
            It.IsAny<CommandFlags>()))
            .ReturnsAsync(true);

        // Act
        var result = await store.UpdateJobStatusAsync(jobId, JobStatus.FetchingDeals, null, "Fetching store deals");

        // Assert
        result.Should().NotBeNull();
        result!.Status.Should().Be(JobStatus.FetchingDeals);
        result.StageDescription.Should().Be("Fetching store deals");
        result.CreatedAt.Should().Be(initialCreatedAt);
        result.UpdatedAt.Should().BeAfter(initialCreatedAt);

        _dbMock.Verify(db => db.StringSetAsync(
            (RedisKey)$"mealshopper:jobs:{jobId}",
            It.Is<RedisValue>(v => v.ToString().Contains("fetchingDeals") || v.ToString().Contains("FetchingDeals")),
            TimeSpan.FromHours(24),
            It.IsAny<bool>(),
            It.IsAny<When>(),
            It.IsAny<CommandFlags>()), Times.Once);
    }

    [Fact]
    public async Task UpdateJobStatusAsync_WhenKeyDoesNotExist_ReturnsNull()
    {
        // Arrange
        var store = new RedisJobStateStore(_redisMock.Object, _config, _loggerMock.Object);
        var jobId = Guid.NewGuid();

        _dbMock.Setup(db => db.StringGetAsync((RedisKey)$"mealshopper:jobs:{jobId}", It.IsAny<CommandFlags>()))
            .ReturnsAsync(RedisValue.Null);

        // Act
        var result = await store.UpdateJobStatusAsync(jobId, JobStatus.Failed, "Error");

        // Assert
        result.Should().BeNull();
    }

    [Fact]
    public async Task CompleteJobAsync_WhenKeyExists_SetsCompletedStatusAndResult()
    {
        // Arrange
        var store = new RedisJobStateStore(_redisMock.Object, _config, _loggerMock.Object);
        var jobId = Guid.NewGuid();
        var initialJob = new JobRecord
        {
            JobId = jobId,
            Status = JobStatus.GeneratingMealPlan,
            CreatedAt = DateTimeOffset.UtcNow.AddMinutes(-2),
            UpdatedAt = DateTimeOffset.UtcNow.AddMinutes(-2)
        };

        var initialJson = JsonSerializer.Serialize(initialJob, new JsonSerializerOptions { PropertyNamingPolicy = JsonNamingPolicy.CamelCase });

        _dbMock.Setup(db => db.StringGetAsync((RedisKey)$"mealshopper:jobs:{jobId}", It.IsAny<CommandFlags>()))
            .ReturnsAsync((RedisValue)initialJson);

        _dbMock.Setup(db => db.StringSetAsync(
            (RedisKey)$"mealshopper:jobs:{jobId}",
            It.IsAny<RedisValue>(),
            TimeSpan.FromHours(24),
            It.IsAny<bool>(),
            It.IsAny<When>(),
            It.IsAny<CommandFlags>()))
            .ReturnsAsync(true);

        var mealPlanResult = new MealPlanResultDto
        {
            MealPlanId = "plan-123",
            EstimatedTotalTripCost = 45.50m,
            TotalTravelTimeMinutes = 20,
            RequiredStores = new List<string> { "Trader Joe's" },
            Recipes = new List<RecipeCardDto>()
        };

        // Act
        var result = await store.CompleteJobAsync(jobId, mealPlanResult);

        // Assert
        result.Should().NotBeNull();
        result!.Status.Should().Be(JobStatus.Completed);
        result.StageDescription.Should().Be("Meal plan generated successfully.");
        result.Result.Should().NotBeNull();
        result.Result!.MealPlanId.Should().Be("plan-123");
        result.Result.EstimatedTotalTripCost.Should().Be(45.50m);
    }

    [Fact]
    public async Task CompleteJobAsync_WhenKeyDoesNotExist_ReturnsNull()
    {
        // Arrange
        var store = new RedisJobStateStore(_redisMock.Object, _config, _loggerMock.Object);
        var jobId = Guid.NewGuid();

        _dbMock.Setup(db => db.StringGetAsync((RedisKey)$"mealshopper:jobs:{jobId}", It.IsAny<CommandFlags>()))
            .ReturnsAsync(RedisValue.Null);

        var mealPlanResult = new MealPlanResultDto { MealPlanId = "plan-123" };

        // Act
        var result = await store.CompleteJobAsync(jobId, mealPlanResult);

        // Assert
        result.Should().BeNull();
    }

    [Fact]
    public async Task RedisException_OnCreateJob_ThrowsDomainException()
    {
        // Arrange
        var store = new RedisJobStateStore(_redisMock.Object, _config, _loggerMock.Object);
        var job = new JobRecord { JobId = Guid.NewGuid() };

        _dbMock.Setup(db => db.StringSetAsync(
            It.IsAny<RedisKey>(),
            It.IsAny<RedisValue>(),
            It.IsAny<TimeSpan?>(),
            It.IsAny<bool>(),
            It.IsAny<When>(),
            It.IsAny<CommandFlags>()))
            .ThrowsAsync(new RedisTimeoutException("Redis timed out", CommandStatus.Unknown));

        // Act
        var act = async () => await store.CreateJobAsync(job);

        // Assert
        await act.Should().ThrowAsync<DomainException>()
            .WithMessage($"*Failed to create job {job.JobId} in Redis state store.*");
    }

    [Fact]
    public async Task RedisException_OnGetJob_ThrowsDomainException()
    {
        // Arrange
        var store = new RedisJobStateStore(_redisMock.Object, _config, _loggerMock.Object);
        var jobId = Guid.NewGuid();

        _dbMock.Setup(db => db.StringGetAsync(It.IsAny<RedisKey>(), It.IsAny<CommandFlags>()))
            .ThrowsAsync(new RedisConnectionException(ConnectionFailureType.UnableToConnect, "Cannot connect"));

        // Act
        var act = async () => await store.GetJobAsync(jobId);

        // Assert
        await act.Should().ThrowAsync<DomainException>()
            .WithMessage($"*Failed to retrieve job {jobId} from Redis state store.*");
    }

    [Fact]
    public async Task RedisException_OnUpdateJobStatus_ThrowsDomainException()
    {
        // Arrange
        var store = new RedisJobStateStore(_redisMock.Object, _config, _loggerMock.Object);
        var jobId = Guid.NewGuid();

        _dbMock.Setup(db => db.StringGetAsync(It.IsAny<RedisKey>(), It.IsAny<CommandFlags>()))
            .ThrowsAsync(new RedisServerException("ERR server error"));

        // Act
        var act = async () => await store.UpdateJobStatusAsync(jobId, JobStatus.Completed);

        // Assert
        await act.Should().ThrowAsync<DomainException>()
            .WithMessage($"*Failed to update status for job {jobId} in Redis state store.*");
    }

    [Fact]
    public async Task RedisException_OnCompleteJob_ThrowsDomainException()
    {
        // Arrange
        var store = new RedisJobStateStore(_redisMock.Object, _config, _loggerMock.Object);
        var jobId = Guid.NewGuid();

        _dbMock.Setup(db => db.StringGetAsync(It.IsAny<RedisKey>(), It.IsAny<CommandFlags>()))
            .ThrowsAsync(new RedisServerException("ERR server error"));

        // Act
        var act = async () => await store.CompleteJobAsync(jobId, new MealPlanResultDto());

        // Assert
        await act.Should().ThrowAsync<DomainException>()
            .WithMessage($"*Failed to complete job {jobId} in Redis state store.*");
    }

    [Fact]
    public async Task KeyFormat_UsesDefaultInstanceName_WhenConfigMissing()
    {
        // Arrange
        var emptyConfig = new ConfigurationBuilder().Build();
        var store = new RedisJobStateStore(_redisMock.Object, emptyConfig, _loggerMock.Object);
        var jobId = Guid.NewGuid();

        _dbMock.Setup(db => db.StringGetAsync(It.IsAny<RedisKey>(), It.IsAny<CommandFlags>()))
            .ReturnsAsync(RedisValue.Null);

        // Act
        await store.GetJobAsync(jobId);

        // Assert
        _dbMock.Verify(db => db.StringGetAsync((RedisKey)$"mealshopper:jobs:{jobId}", It.IsAny<CommandFlags>()), Times.Once);
    }
}
