namespace MealShopper.Identity.Models;

/// <summary>
/// Represents a registered client application in the identity service.
/// </summary>
public class ClientApplication
{
    /// <summary>
    /// Unique identifier for the client application.
    /// </summary>
    public string ClientId { get; set; } = string.Empty;

    /// <summary>
    /// Secure PBKDF2 hash of the client secret.
    /// </summary>
    public string ClientSecretHash { get; set; } = string.Empty;

    /// <summary>
    /// Display name of the client application.
    /// </summary>
    public string ClientName { get; set; } = string.Empty;

    /// <summary>
    /// List of scopes this client is authorized to request.
    /// </summary>
    public List<string> AllowedScopes { get; set; } = [];

    /// <summary>
    /// Indicates whether the client application is active.
    /// </summary>
    public bool IsActive { get; set; } = true;

    /// <summary>
    /// Timestamp when the client application was registered.
    /// </summary>
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;
}
