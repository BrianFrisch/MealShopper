using System.ComponentModel.DataAnnotations;

namespace MealShopper.Orchestrator.Models.DTOs;

/// <summary>
/// Represents the intake request payload for discovering store deals based on user location and search constraints.
/// </summary>
public class MealPlanDiscoveryRequest : IValidatableObject
{
    private static readonly HashSet<int> AllowedRadiusMiles = new() { 1, 2, 5, 7, 10 };

    /// <summary>
    /// User location address used for store discovery.
    /// </summary>
    [Required(ErrorMessage = "Address is required.")]
    public AddressDto Address { get; set; } = new();

    /// <summary>
    /// Search radius in miles for local store discovery. Allowed values: 1, 2, 5, 7, 10 (default 5).
    /// </summary>
    public int SearchRadiusMiles { get; set; } = 5;

    /// <summary>
    /// Maximum number of stores to visit for discovering deals. Allowed range: 1 to 4 (default 2).
    /// </summary>
    [Range(1, 4, ErrorMessage = "MaxStores must be between 1 and 4.")]
    public int MaxStores { get; set; } = 2;

    public virtual IEnumerable<ValidationResult> Validate(ValidationContext validationContext)
    {
        if (!AllowedRadiusMiles.Contains(SearchRadiusMiles))
        {
            yield return new ValidationResult(
                $"SearchRadiusMiles must be one of the allowed values: {string.Join(", ", AllowedRadiusMiles)}.",
                new[] { nameof(SearchRadiusMiles) });
        }
    }
}
