using MealShopper.Identity.Models;

namespace MealShopper.Identity.Services;

/// <summary>
/// Service interface for generating signed security tokens.
/// </summary>
public interface ITokenService
{
    /// <summary>
    /// Creates a signed JWT access token for a subject with the specified claims, roles, and scopes.
    /// </summary>
    /// <param name="subject">Unique user/client identifier (sub).</param>
    /// <param name="email">User email address.</param>
    /// <param name="roles">User roles.</param>
    /// <param name="scopes">Granted permission scopes.</param>
    /// <param name="ct">Cancellation token.</param>
    /// <returns>A <see cref="TokenResult"/> containing the access token and lifetime information.</returns>
    Task<TokenResult> CreateAccessTokenAsync(
        string subject,
        string email,
        IEnumerable<string> roles,
        IEnumerable<string> scopes,
        CancellationToken ct = default);

    /// <summary>
    /// Creates a signed JWT machine-to-machine client access token for client credentials grant.
    /// </summary>
    /// <param name="clientId">Unique client application identifier (sub and client_id).</param>
    /// <param name="authorizedScopes">Authorized permission scopes.</param>
    /// <param name="ct">Cancellation token.</param>
    /// <returns>A <see cref="TokenResult"/> containing the machine-to-machine access token.</returns>
    Task<TokenResult> CreateClientTokenAsync(
        string clientId,
        IEnumerable<string> authorizedScopes,
        CancellationToken ct = default);
}
