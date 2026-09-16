using MealShopper.Identity.Models;

namespace MealShopper.Identity.Services;

/// <summary>
/// Service interface for issuing, retrieving, and revoking refresh tokens.
/// </summary>
public interface IRefreshTokenStore
{
    /// <summary>
    /// Generates and stores a new cryptographically random refresh token for a user.
    /// </summary>
    /// <param name="userId">Unique user ID.</param>
    /// <param name="ct">Cancellation token.</param>
    /// <returns>The generated refresh token string.</returns>
    Task<string> CreateRefreshTokenAsync(Guid userId, CancellationToken ct = default);

    /// <summary>
    /// Retrieves a refresh token record by token string.
    /// </summary>
    /// <param name="token">Refresh token string.</param>
    /// <param name="ct">Cancellation token.</param>
    /// <returns>The token record if found; otherwise null.</returns>
    Task<RefreshTokenRecord?> GetRefreshTokenAsync(string token, CancellationToken ct = default);

    /// <summary>
    /// Marks a refresh token as revoked.
    /// </summary>
    /// <param name="token">Refresh token string to revoke.</param>
    /// <param name="ct">Cancellation token.</param>
    Task RevokeRefreshTokenAsync(string token, CancellationToken ct = default);
}
