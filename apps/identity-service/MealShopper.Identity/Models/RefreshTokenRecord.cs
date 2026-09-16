namespace MealShopper.Identity.Models;

/// <summary>
/// Represents a stored refresh token record associated with a user identity.
/// </summary>
public class RefreshTokenRecord
{
    /// <summary>
    /// Secure cryptographically random base64 string identifying the token.
    /// </summary>
    public string Token { get; set; } = string.Empty;

    /// <summary>
    /// Identifier of the user account associated with this token.
    /// </summary>
    public Guid UserId { get; set; }

    /// <summary>
    /// Timestamp when this token expires (e.g. 7 days).
    /// </summary>
    public DateTimeOffset ExpiryDate { get; set; }

    /// <summary>
    /// Flag indicating if the refresh token has been revoked.
    /// </summary>
    public bool IsRevoked { get; set; }
}
