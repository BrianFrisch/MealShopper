namespace MealShopper.Orchestrator.Infrastructure.Security;

/// <summary>
/// Service for acquiring and caching machine-to-machine (M2M) OAuth2 access tokens.
/// </summary>
public interface ITokenAcquisitionService
{
    /// <summary>
    /// Gets a valid cached or freshly issued OAuth2 access token for the specified scope.
    /// </summary>
    /// <param name="scope">Requested permission scope(s).</param>
    /// <param name="ct">Cancellation token.</param>
    /// <returns>Signed JWT access token string.</returns>
    Task<string> GetAccessTokenAsync(string scope, CancellationToken ct = default);
}
