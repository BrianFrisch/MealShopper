using MealShopper.Orchestrator.Clients;
using MealShopper.Orchestrator.Common.Security;
using MealShopper.Orchestrator.Infrastructure.Security;
using MealShopper.Orchestrator.Services;
using Microsoft.Extensions.Caching.Memory;
using Microsoft.Extensions.Http.Resilience;
using Polly;

var builder = WebApplication.CreateBuilder(args);

// Add services to the container.
builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();
builder.Services.AddHttpContextAccessor();

// Register gateway user security context
builder.Services.AddScoped<IGatewayUserContext, GatewayUserContext>();

// Register memory cache and M2M token acquisition service
builder.Services.AddMemoryCache();
builder.Services.AddHttpClient("M2MTokenClient");
builder.Services.AddSingleton<ITokenAcquisitionService>(sp =>
{
    var httpClientFactory = sp.GetRequiredService<IHttpClientFactory>();
    var memoryCache = sp.GetRequiredService<IMemoryCache>();
    var configuration = sp.GetRequiredService<IConfiguration>();
    var logger = sp.GetRequiredService<ILogger<ClientCredentialsTokenAcquisitionService>>();
    return new ClientCredentialsTokenAcquisitionService(
        httpClientFactory.CreateClient("M2MTokenClient"),
        memoryCache,
        configuration,
        logger);
});

// Register typed HTTP clients with Polly resilience pipelines
builder.Services.AddHttpClient<IShopperClient, ShopperClient>(client =>
{
    var shopperUrl = builder.Configuration["Services:ShopperUrl"] 
        ?? builder.Configuration["Services:ShopperDomainUrl"] 
        ?? "http://localhost:8001";
    client.BaseAddress = new Uri(shopperUrl.TrimEnd('/') + "/");
})
.AddHttpMessageHandler(sp =>
{
    var tokenService = sp.GetRequiredService<ITokenAcquisitionService>();
    var logger = sp.GetRequiredService<ILogger<M2MAuthenticationHandler>>();
    return new M2MAuthenticationHandler(tokenService, "shopper.read", logger);
})
.AddResilienceHandler("shopper-pipeline", (pipelineBuilder, context) =>
{
    var loggerFactory = context.ServiceProvider.GetRequiredService<ILoggerFactory>();
    var logger = loggerFactory.CreateLogger("Polly.ShopperPipeline");

    pipelineBuilder.AddRetry(new HttpRetryStrategyOptions
    {
        MaxRetryAttempts = 3,
        BackoffType = DelayBackoffType.Exponential,
        UseJitter = true,
        Delay = TimeSpan.FromMilliseconds(500),
        OnRetry = args =>
        {
            logger.LogWarning(
                "Shopper Domain request failed. Retrying attempt {AttemptNumber} after {RetryDelay}ms. Reason: {ErrorMessage}",
                args.AttemptNumber,
                args.RetryDelay.TotalMilliseconds,
                args.Outcome.Exception?.Message ?? $"HTTP status {args.Outcome.Result?.StatusCode}");
            return ValueTask.CompletedTask;
        }
    });

    pipelineBuilder.AddCircuitBreaker(new HttpCircuitBreakerStrategyOptions
    {
        SamplingDuration = TimeSpan.FromSeconds(30),
        FailureRatio = 0.5,
        MinimumThroughput = 5,
        BreakDuration = TimeSpan.FromSeconds(15),
        OnOpened = args =>
        {
            logger.LogWarning(
                "Shopper Domain circuit breaker opened for {BreakDuration}s. Reason: {ErrorMessage}",
                args.BreakDuration.TotalSeconds,
                args.Outcome.Exception?.Message ?? $"HTTP status {args.Outcome.Result?.StatusCode}");
            return ValueTask.CompletedTask;
        }
    });

    pipelineBuilder.AddTimeout(new HttpTimeoutStrategyOptions
    {
        Timeout = TimeSpan.FromSeconds(10)
    });
});

builder.Services.AddHttpClient<IPlanningClient, PlanningClient>(client =>
{
    var plannerUrl = builder.Configuration["Services:PlannerUrl"]
        ?? builder.Configuration["Services:PlanningDomainUrl"]
        ?? "http://localhost:8002";
    client.BaseAddress = new Uri(plannerUrl.TrimEnd('/') + "/");
})
.AddHttpMessageHandler(sp =>
{
    var tokenService = sp.GetRequiredService<ITokenAcquisitionService>();
    var logger = sp.GetRequiredService<ILogger<M2MAuthenticationHandler>>();
    return new M2MAuthenticationHandler(tokenService, "planner.generate", logger);
})
.AddResilienceHandler("planning-pipeline", (pipelineBuilder, context) =>
{
    var loggerFactory = context.ServiceProvider.GetRequiredService<ILoggerFactory>();
    var logger = loggerFactory.CreateLogger("Polly.PlanningPipeline");

    pipelineBuilder.AddRetry(new HttpRetryStrategyOptions
    {
        MaxRetryAttempts = 2,
        BackoffType = DelayBackoffType.Exponential,
        Delay = TimeSpan.FromSeconds(2),
        OnRetry = args =>
        {
            logger.LogWarning(
                "Planning Domain request failed. Retrying attempt {AttemptNumber} after {RetryDelay}ms. Reason: {ErrorMessage}",
                args.AttemptNumber,
                args.RetryDelay.TotalMilliseconds,
                args.Outcome.Exception?.Message ?? $"HTTP status {args.Outcome.Result?.StatusCode}");
            return ValueTask.CompletedTask;
        }
    });

    pipelineBuilder.AddCircuitBreaker(new HttpCircuitBreakerStrategyOptions
    {
        SamplingDuration = TimeSpan.FromSeconds(60),
        FailureRatio = 0.5,
        BreakDuration = TimeSpan.FromSeconds(30),
        OnOpened = args =>
        {
            logger.LogWarning(
                "Planning Domain circuit breaker opened for {BreakDuration}s. Reason: {ErrorMessage}",
                args.BreakDuration.TotalSeconds,
                args.Outcome.Exception?.Message ?? $"HTTP status {args.Outcome.Result?.StatusCode}");
            return ValueTask.CompletedTask;
        }
    });

    pipelineBuilder.AddTimeout(new HttpTimeoutStrategyOptions
    {
        Timeout = TimeSpan.FromSeconds(75)
    });
});

builder.Services.AddHttpClient<IPlannerClient, PlannerClient>(client =>
{
    var plannerUrl = builder.Configuration["Services:PlannerUrl"]
        ?? builder.Configuration["Services:PlanningDomainUrl"]
        ?? "http://localhost:8002";
    client.BaseAddress = new Uri(plannerUrl.TrimEnd('/') + "/");
})
.AddHttpMessageHandler(sp =>
{
    var tokenService = sp.GetRequiredService<ITokenAcquisitionService>();
    var logger = sp.GetRequiredService<ILogger<M2MAuthenticationHandler>>();
    return new M2MAuthenticationHandler(tokenService, "planner.generate", logger);
});

// Register job state tracking services
builder.Services.AddSingleton<InMemoryJobTracker>();
builder.Services.AddSingleton<IJobStateStore>(sp => sp.GetRequiredService<InMemoryJobTracker>());
builder.Services.AddSingleton<IJobTracker>(sp => sp.GetRequiredService<InMemoryJobTracker>());

// Register workflow orchestrator
builder.Services.AddScoped<IMealPlanOrchestrator, MealPlanOrchestrator>();

var app = builder.Build();

// Configure the HTTP request pipeline.
if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseHttpsRedirection();

app.UseAuthorization();

app.MapControllers();

app.Run();
