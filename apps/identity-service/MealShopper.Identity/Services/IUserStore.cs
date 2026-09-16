using MealShopper.Identity.Models;

namespace MealShopper.Identity.Services;

/// <summary>
/// Service interface for querying and creating user identity records.
/// </summary>
public interface IUserStore
{
    /// <summary>
    /// Finds a user by email address (case-insensitive).
    /// </summary>
    /// <param name="email">Email address to search for.</param>
    /// <param name="ct">Cancellation token.</param>
    /// <returns>The matching <see cref="ApplicationUser"/> if found; otherwise null.</returns>
    Task<ApplicationUser?> FindByEmailAsync(string email, CancellationToken ct = default);

    /// <summary>
    /// Creates and persists a new user with hashed credentials and roles.
    /// </summary>
    /// <param name="email">User email address.</param>
    /// <param name="password">Plain text password to be hashed.</param>
    /// <param name="roles">Assigned roles.</param>
    /// <param name="ct">Cancellation token.</param>
    /// <returns>The newly created <see cref="ApplicationUser"/>.</returns>
    Task<ApplicationUser> CreateUserAsync(string email, string password, List<string> roles, CancellationToken ct = default);
}
