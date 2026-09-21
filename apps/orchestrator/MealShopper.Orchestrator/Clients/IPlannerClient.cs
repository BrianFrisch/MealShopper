using MealShopper.Orchestrator.Models.Domain;

namespace MealShopper.Orchestrator.Clients;

public interface IPlannerClient
{
    Task<MealPlanResponseDto> GeneratePlanAsync(MealPlanRequestDto req, CancellationToken ct = default);
}
