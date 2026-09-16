using System.Text.Json.Serialization;

namespace MealShopper.Identity.Models.DTOs;

/// <summary>
/// OAuth 2.0 / OpenID Connect token endpoint response payload.
/// </summary>
public class TokenResponse
{
    /// <summary>
    /// Signed JWT access token.
    /// </summary>
    [JsonPropertyName("access_token")]
    public string AccessToken { get; set; } = string.Empty;

    /// <summary>
    /// Token type (Bearer).
    /// </summary>
    [JsonPropertyName("token_type")]
    public string TokenType { get; set; } = "Bearer";

    /// <summary>
    /// Token lifetime in seconds.
    /// </summary>
    [JsonPropertyName("expires_in")]
    public int ExpiresIn { get; set; } = 900;

    /// <summary>
    /// Cryptographically random single-use refresh token.
    /// </summary>
    [JsonPropertyName("refresh_token")]
    public string RefreshToken { get; set; } = string.Empty;
}
