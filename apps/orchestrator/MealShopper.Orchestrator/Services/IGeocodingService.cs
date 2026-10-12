using MealShopper.Orchestrator.Models.DTOs;
namespace MealShopper.Orchestrator.Services;

public interface IGeocodingService
{
    Task<(double Latitude, double Longitude)> ResolveCoordinatesAsync(
        AddressDto address, 
        CancellationToken ct = default);
}