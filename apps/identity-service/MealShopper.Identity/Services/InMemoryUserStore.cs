using System.Collections.Concurrent;
using MealShopper.Identity.Models;

namespace MealShopper.Identity.Services;

/// <summary>
/// In-memory implementation of <see cref="IUserStore"/> pre-seeded with default test user.
/// </summary>
public class InMemoryUserStore : IUserStore
{
    private readonly ConcurrentDictionary<string, ApplicationUser> _usersByNormalizedEmail = new();
    private readonly IPasswordHasher _passwordHasher;

    public InMemoryUserStore(IPasswordHasher passwordHasher)
    {
        _passwordHasher = passwordHasher ?? throw new ArgumentNullException(nameof(passwordHasher));

        // Pre-seed default test user: "testuser@mealshopper.local" / "P@ssword123!"
        var defaultEmail = "testuser@mealshopper.local";
        var defaultUser = new ApplicationUser
        {
            Id = Guid.NewGuid(),
            Email = defaultEmail,
            NormalizedEmail = defaultEmail.ToUpperInvariant(),
            PasswordHash = _passwordHasher.HashPassword("P@ssword123!"),
            Roles = ["User"],
            CreatedAt = DateTimeOffset.UtcNow
        };

        _usersByNormalizedEmail[defaultUser.NormalizedEmail] = defaultUser;
    }

    /// <inheritdoc />
    public Task<ApplicationUser?> FindByEmailAsync(string email, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(email))
        {
            return Task.FromResult<ApplicationUser?>(null);
        }

        var normalizedEmail = email.Trim().ToUpperInvariant();
        _usersByNormalizedEmail.TryGetValue(normalizedEmail, out var user);
        return Task.FromResult(user);
    }

    /// <inheritdoc />
    public Task<ApplicationUser> CreateUserAsync(
        string email,
        string password,
        List<string> roles,
        CancellationToken ct = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(email);
        ArgumentException.ThrowIfNullOrWhiteSpace(password);

        var normalizedEmail = email.Trim().ToUpperInvariant();

        if (_usersByNormalizedEmail.ContainsKey(normalizedEmail))
        {
            throw new InvalidOperationException($"User with email '{email}' already exists.");
        }

        var user = new ApplicationUser
        {
            Id = Guid.NewGuid(),
            Email = email.Trim(),
            NormalizedEmail = normalizedEmail,
            PasswordHash = _passwordHasher.HashPassword(password),
            Roles = roles ?? ["User"],
            CreatedAt = DateTimeOffset.UtcNow
        };

        _usersByNormalizedEmail[normalizedEmail] = user;
        return Task.FromResult(user);
    }
}
