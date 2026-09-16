using System.Text.Json.Serialization;
using Microsoft.AspNetCore.Mvc;

namespace MealShopper.Identity.Models.DTOs;

/// <summary>
/// OAuth 2.0 / OpenID Connect token endpoint request payload.
/// </summary>
public class TokenRequest
{
    /// <summary>
    /// Grant type for authorization ("password" or "refresh_token").
    /// </summary>
    [FromForm(Name = "grant_type")]
    [JsonPropertyName("grant_type")]
    public string GrantType { get; set; } = string.Empty;

    /// <summary>
    /// User email address (required for "password" grant).
    /// </summary>
    [FromForm(Name = "email")]
    [JsonPropertyName("email")]
    public string? Email { get; set; }

    /// <summary>
    /// User password (required for "password" grant).
    /// </summary>
    [FromForm(Name = "password")]
    [JsonPropertyName("password")]
    public string? Password { get; set; }

    /// <summary>
    /// Refresh token string (required for "refresh_token" grant).
    /// </summary>
    [FromForm(Name = "refresh_token")]
    [JsonPropertyName("refresh_token")]
    public string? RefreshToken { get; set; }

    /// <summary>
    /// Client application identifier (required or optional for client_credentials grant).
    /// </summary>
    [FromForm(Name = "client_id")]
    [JsonPropertyName("client_id")]
    public string? ClientId { get; set; }

    /// <summary>
    /// Client application secret (required or optional for client_credentials grant).
    /// </summary>
    [FromForm(Name = "client_secret")]
    [JsonPropertyName("client_secret")]
    public string? ClientSecret { get; set; }

    /// <summary>
    /// Requested authorization scope(s).
    /// </summary>
    [FromForm(Name = "scope")]
    [JsonPropertyName("scope")]
    public string? Scope { get; set; }
}
