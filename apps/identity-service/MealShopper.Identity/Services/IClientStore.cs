using MealShopper.Identity.Models;

namespace MealShopper.Identity.Services;

/// <summary>
/// Service interface for querying and validating client application credentials.
/// </summary>
public interface IClientStore
{
    /// <summary>
    /// Finds a registered client application by its client ID.
    /// </summary>
    /// <param name="clientId">Unique client application identifier.</param>
    /// <param name="ct">Cancellation token.</param>
    /// <returns>The matching <see cref="ClientApplication"/> if found; otherwise null.</returns>
    Task<ClientApplication?> FindClientByIdAsync(string clientId, CancellationToken ct = default);

    /// <summary>
    /// Validates client credentials against the stored client secret hash.
    /// </summary>
    /// <param name="clientId">Unique client application identifier.</param>
    /// <param name="clientSecret">Plaintext client secret.</param>
    /// <param name="ct">Cancellation token.</param>
    /// <returns>True if the client credentials are valid; otherwise false.</returns>
    Task<bool> ValidateClientCredentialsAsync(string clientId, string clientSecret, CancellationToken ct = default);
}
