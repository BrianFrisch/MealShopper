using System.Collections.Concurrent;
using System.Security.Cryptography;
using MealShopper.Identity.Models;
using Microsoft.IdentityModel.Tokens;

namespace MealShopper.Identity.Services;

/// <summary>
/// Thread-safe in-memory store for managing refresh tokens using ConcurrentDictionary.
/// </summary>
public class InMemoryRefreshTokenStore : IRefreshTokenStore
{
    private static readonly TimeSpan DefaultRefreshTokenLifetime = TimeSpan.FromDays(7);
    private readonly ConcurrentDictionary<string, RefreshTokenRecord> _refreshTokens = new();

    /// <inheritdoc />
    public Task<string> CreateRefreshTokenAsync(Guid userId, CancellationToken ct = default)
    {
        var randomBytes = RandomNumberGenerator.GetBytes(64);
        var token = Base64UrlEncoder.Encode(randomBytes);

        var record = new RefreshTokenRecord
        {
            Token = token,
            UserId = userId,
            ExpiryDate = DateTimeOffset.UtcNow.Add(DefaultRefreshTokenLifetime),
            IsRevoked = false
        };

        _refreshTokens[token] = record;
        return Task.FromResult(token);
    }

    /// <inheritdoc />
    public Task<RefreshTokenRecord?> GetRefreshTokenAsync(string token, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(token))
        {
            return Task.FromResult<RefreshTokenRecord?>(null);
        }

        _refreshTokens.TryGetValue(token, out var record);
        return Task.FromResult(record);
    }

    /// <inheritdoc />
    public Task RevokeRefreshTokenAsync(string token, CancellationToken ct = default)
    {
        if (!string.IsNullOrWhiteSpace(token) && _refreshTokens.TryGetValue(token, out var record))
        {
            record.IsRevoked = true;
        }

        return Task.CompletedTask;
    }
}
