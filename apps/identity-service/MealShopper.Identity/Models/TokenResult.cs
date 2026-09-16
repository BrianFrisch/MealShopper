namespace MealShopper.Identity.Models;

/// <summary>
/// Represents the result of an access token generation operation.
/// </summary>
public class TokenResult
{
    /// <summary>
    /// The signed JWT access token.
    /// </summary>
    public string AccessToken { get; set; } = string.Empty;

    /// <summary>
    /// The token type (defaults to "Bearer").
    /// </summary>
    public string TokenType { get; set; } = "Bearer";

    /// <summary>
    /// The lifetime of the token in seconds.
    /// </summary>
    public int ExpiresIn { get; set; }

    /// <summary>
    /// Optional refresh token for obtaining new access tokens.
    /// </summary>
    public string? RefreshToken { get; set; }
}
