using System.Text.Json;
using Microsoft.Extensions.Caching.Distributed;
using MealShopper.Identity.Models;

namespace MealShopper.Identity.Services;

/// <summary>
/// Distributed cache implementation of <see cref="IUserStore"/> backed by <see cref="IDistributedCache"/>.
/// Suitable for horizontal scaling across cloud providers and multi-instance deployments.
/// </summary>
public class DistributedCacheUserStore : IUserStore
{
    private readonly IDistributedCache _cache;
    private readonly IPasswordHasher _passwordHasher;

    private static readonly DistributedCacheEntryOptions CacheOptions = new()
    {
        // 24-hour sliding expiration for user sessions in the cache
        SlidingExpiration = TimeSpan.FromHours(24)
    };

    public DistributedCacheUserStore(IDistributedCache cache, IPasswordHasher passwordHasher)
    {
        _cache = cache ?? throw new ArgumentNullException(nameof(cache));
        _passwordHasher = passwordHasher ?? throw new ArgumentNullException(nameof(passwordHasher));

        // Pre-seed default test user if missing: "testuser@mealshopper.local" / "P@ssword123!"
        SeedDefaultUserAsync().GetAwaiter().GetResult();
    }

    /// <inheritdoc />
    public async Task<ApplicationUser?> FindByEmailAsync(string email, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(email))
        {
            return null;
        }

        var normalizedEmail = email.Trim().ToUpperInvariant();
        var emailIndexKey = $"idx:user:email:{normalizedEmail}";

        var userId = await _cache.GetStringAsync(emailIndexKey, ct);
        if (string.IsNullOrEmpty(userId))
        {
            return null;
        }

        var userKey = $"user:{userId}";
        var json = await _cache.GetStringAsync(userKey, ct);
        if (string.IsNullOrEmpty(json))
        {
            return null;
        }

        return JsonSerializer.Deserialize<ApplicationUser>(json);
    }

    /// <inheritdoc />
    public async Task<ApplicationUser> CreateUserAsync(
        string email,
        string password,
        List<string> roles,
        CancellationToken ct = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(email);
        ArgumentException.ThrowIfNullOrWhiteSpace(password);

        var normalizedEmail = email.Trim().ToUpperInvariant();
        var emailIndexKey = $"idx:user:email:{normalizedEmail}";

        var existingUserId = await _cache.GetStringAsync(emailIndexKey, ct);
        if (!string.IsNullOrEmpty(existingUserId))
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

        var userKey = $"user:{user.Id}";
        var json = JsonSerializer.Serialize(user);

        // Store primary entity and secondary email lookup index
        await _cache.SetStringAsync(userKey, json, CacheOptions, ct);
        await _cache.SetStringAsync(emailIndexKey, user.Id.ToString(), CacheOptions, ct);

        return user;
    }

    private async Task SeedDefaultUserAsync()
    {
        var defaultEmail = "testuser@mealshopper.local";
        var normalizedEmail = defaultEmail.ToUpperInvariant();
        var emailIndexKey = $"idx:user:email:{normalizedEmail}";

        var existing = await _cache.GetStringAsync(emailIndexKey);
        if (string.IsNullOrEmpty(existing))
        {
            var user = new ApplicationUser
            {
                Id = Guid.NewGuid(),
                Email = defaultEmail,
                NormalizedEmail = normalizedEmail,
                PasswordHash = _passwordHasher.HashPassword("P@ssword123!"),
                Roles = ["User"],
                CreatedAt = DateTimeOffset.UtcNow
            };

            var userKey = $"user:{user.Id}";
            var json = JsonSerializer.Serialize(user);

            await _cache.SetStringAsync(userKey, json, CacheOptions);
            await _cache.SetStringAsync(emailIndexKey, user.Id.ToString(), CacheOptions);
        }
    }
}