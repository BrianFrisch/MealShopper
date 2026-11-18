using System.ComponentModel.DataAnnotations;
using System.Text.RegularExpressions;

namespace MealShopper.Orchestrator.Models.DTOs;

/// <summary>
/// Represents address information for locating nearby grocery stores.
/// </summary>
public class AddressDto : IValidatableObject
{
    private static readonly Regex ZipCodeRegex = new(@"^\d{5}(-\d{4})?$", RegexOptions.Compiled);

    /// <summary>
    /// Street address (optional).
    /// </summary>
    public string? Street { get; set; }

    /// <summary>
    /// City name (optional).
    /// </summary>
    public string? City { get; set; }

    /// <summary>
    /// State abbreviation or name (optional).
    /// </summary>
    public string? State { get; set; }

    /// <summary>
    /// US Zip Code (5-digit or 9-digit ZIP+4, optional if City and State or Coordinates are provided).
    /// </summary>
    public string? ZipCode { get; set; }

    /// <summary>
    /// Latitude in decimal degrees (optional).
    /// </summary>
    public double? Latitude { get; set; }

    /// <summary>
    /// Longitude in decimal degrees (optional).
    /// </summary>
    public double? Longitude { get; set; }

    public IEnumerable<ValidationResult> Validate(ValidationContext validationContext)
    {
        var hasCoordinates = Latitude.HasValue && Longitude.HasValue;
        var hasZip = !string.IsNullOrWhiteSpace(ZipCode);
        var hasCityAndState = !string.IsNullOrWhiteSpace(City) && !string.IsNullOrWhiteSpace(State);

        if (!hasCoordinates && !hasZip && !hasCityAndState)
        {
            yield return new ValidationResult(
                "Either a valid ZipCode, or City and State, or Latitude and Longitude must be provided.",
                new[] { nameof(ZipCode), nameof(City), nameof(State) });
        }

        if (hasZip && !ZipCodeRegex.IsMatch(ZipCode!.Trim()))
        {
            yield return new ValidationResult(
                "ZipCode must be a valid 5-digit or 9-digit (ZIP+4) US zip code.",
                new[] { nameof(ZipCode) });
        }
    }
}
