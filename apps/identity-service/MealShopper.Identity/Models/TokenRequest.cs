using System.Text.Json.Serialization;

namespace MealShopper.Identity.Models;

/// <summary>
/// OAuth 2.0 / OpenID Connect token endpoint request payload.
/// </summary>
public class TokenRequest
{
    /// <summary>
    /// Grant type for authorization ("password" or "refresh_token").
    /// </summary>
    [JsonPropertyName("grant_type")]
    public string GrantType { get; set; } = string.Empty;

    /// <summary>
    /// User email address (required for "password" grant).
    /// </summary>
    [JsonPropertyName("email")]
    public string? Email { get; set; }

    /// <summary>
    /// User password (required for "password" grant).
    /// </summary>
    [JsonPropertyName("password")]
    public string? Password { get; set; }

    /// <summary>
    /// Refresh token string (required for "refresh_token" grant).
    /// </summary>
    [JsonPropertyName("refresh_token")]
    public string? RefreshToken { get; set; }
}
