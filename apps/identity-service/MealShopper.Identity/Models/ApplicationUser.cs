namespace MealShopper.Identity.Models;

/// <summary>
/// Represents an application user identity in MealShopper.
/// </summary>
public class ApplicationUser
{
    /// <summary>
    /// Unique identifier for the user.
    /// </summary>
    public Guid Id { get; set; } = Guid.NewGuid();

    /// <summary>
    /// User's email address.
    /// </summary>
    public string Email { get; set; } = string.Empty;

    /// <summary>
    /// Uppercase/normalized email address for case-insensitive lookups.
    /// </summary>
    public string NormalizedEmail { get; set; } = string.Empty;

    /// <summary>
    /// Secure PBKDF2 hash of the user's password.
    /// </summary>
    public string PasswordHash { get; set; } = string.Empty;

    /// <summary>
    /// Assigned authorization roles (e.g. "User", "Admin").
    /// </summary>
    public List<string> Roles { get; set; } = [];

    /// <summary>
    /// Timestamp when the user account was created.
    /// </summary>
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;
}
