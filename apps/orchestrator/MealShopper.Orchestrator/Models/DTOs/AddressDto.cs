using System.ComponentModel.DataAnnotations;

namespace MealShopper.Orchestrator.Models.DTOs;

/// <summary>
/// Represents address information for locating nearby grocery stores.
/// </summary>
public class AddressDto
{
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
    /// US Zip Code (5-digit or 9-digit ZIP+4).
    /// </summary>
    [Required(ErrorMessage = "ZipCode is required.")]
    [RegularExpression(@"^\d{5}(-\d{4})?$", ErrorMessage = "ZipCode must be a valid 5-digit or 9-digit (ZIP+4) US zip code.")]
    public string ZipCode { get; set; } = string.Empty;
}
