using System.Net.Http.Json;
using System.Text.Json;
using MealShopper.Orchestrator.Models.Domain;
using Microsoft.Extensions.Logging;

namespace MealShopper.Orchestrator.Clients;

public class PlannerClient : IPlannerClient
{
    private readonly HttpClient _httpClient;
    private readonly ILogger<PlannerClient> _logger;
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    public PlannerClient(HttpClient httpClient, ILogger<PlannerClient> logger)
    {
        _httpClient = httpClient ?? throw new ArgumentNullException(nameof(httpClient));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    public async Task<MealPlanResponseDto> GeneratePlanAsync(MealPlanRequestDto req, CancellationToken ct = default)
    {
        ArgumentNullException.ThrowIfNull(req);

        _logger.LogInformation(
            "Sending meal plan generation request. ScoredDeals: {DealCount}, TargetMeals: {TargetMealCount}, HouseholdSize: {HouseholdSize}",
            req.ScoredDeals.Count, req.TargetMealCount, req.HouseholdSize);

        try
        {
            using var response = await _httpClient.PostAsJsonAsync("v1/planner/generate", req, JsonOptions, ct);

            if (!response.IsSuccessStatusCode)
            {
                var errorBody = await response.Content.ReadAsStringAsync(ct);
                _logger.LogError(
                    "Meal plan generation failed with status {StatusCode}. Response: {ResponseBody}",
                    response.StatusCode, errorBody);

                throw new HttpRequestException(
                    $"Meal plan generation failed with status code {(int)response.StatusCode} ({response.StatusCode}): {errorBody}",
                    null,
                    response.StatusCode);
            }

            var result = await response.Content.ReadFromJsonAsync<MealPlanResponseDto>(JsonOptions, ct);
            return result ?? new MealPlanResponseDto();
        }
        catch (HttpRequestException ex)
        {
            _logger.LogError(ex, "HTTP request error occurred during meal plan generation.");
            throw;
        }
    }
}
