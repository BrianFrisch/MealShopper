using System.Net.Http.Json;
using MealShopper.Orchestrator.Exceptions;
using MealShopper.Orchestrator.Models.Planner;
using Microsoft.Extensions.Logging;

namespace MealShopper.Orchestrator.Clients;

/// <summary>
/// Typed HTTP client implementation for communicating with the Python Planning Domain service.
/// </summary>
public class PlanningClient : IPlanningClient
{
    private readonly HttpClient _httpClient;
    private readonly ILogger<PlanningClient> _logger;

    public PlanningClient(HttpClient httpClient, ILogger<PlanningClient> logger)
    {
        _httpClient = httpClient ?? throw new ArgumentNullException(nameof(httpClient));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    /// <inheritdoc />
    public async Task<MealPlanDraftResponse> GenerateMealPlanAsync(
        GenerateMealPlanRequest request,
        CancellationToken ct = default)
    {
        ArgumentNullException.ThrowIfNull(request);

        _logger.LogInformation(
            "Generating meal plan draft via Planning Domain. Cuisines: {CuisinesCount}, AvoidIngredients: {AvoidCount}, TopDeals: {DealsCount}, DaysCount: {DaysCount}",
            request.Cuisines.Count,
            request.AvoidIngredients.Count,
            request.TopDeals.Count,
            request.DaysCount);

        try
        {
            using var response = await _httpClient.PostAsJsonAsync("v1/planner/generate", request, ct);

            if (!response.IsSuccessStatusCode)
            {
                var errorBody = await response.Content.ReadAsStringAsync(ct);
                _logger.LogError(
                    "Planning Domain meal plan generation failed with status {StatusCode}. Response: {ResponseBody}",
                    response.StatusCode,
                    errorBody);

                throw new PlanningDomainException(
                    $"Planning Domain returned status code {(int)response.StatusCode} ({response.StatusCode}): {errorBody}",
                    response.StatusCode,
                    errorBody);
            }

            var result = await response.Content.ReadFromJsonAsync<MealPlanDraftResponse>(cancellationToken: ct);
            return result ?? new MealPlanDraftResponse();
        }
        catch (HttpRequestException ex)
        {
            _logger.LogError(ex, "HTTP request error occurred while communicating with Planning Domain generate endpoint.");
            throw new PlanningDomainException("Failed to communicate with Planning Domain service.", ex);
        }
    }
}
