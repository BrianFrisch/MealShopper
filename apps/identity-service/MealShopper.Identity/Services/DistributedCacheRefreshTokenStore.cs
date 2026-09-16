using System.Security.Cryptography;
using System.Text.Json;
using MealShopper.Identity.Models;
using Microsoft.Extensions.Caching.Distributed;
using Microsoft.IdentityModel.Tokens;

namespace MealShopper.Identity.Services;

public class DistributedCacheRefreshTokenStore : IRefreshTokenStore
{
    private static readonly TimeSpan DefaultRefreshTokenLifetime = TimeSpan.FromDays(7);
    private readonly IDistributedCache _cache;
    private readonly ILogger<DistributedCacheRefreshTokenStore> _logger;

    public DistributedCacheRefreshTokenStore(IDistributedCache cache, ILogger<DistributedCacheRefreshTokenStore> logger)
    {
        _cache = cache ?? throw new ArgumentNullException(nameof(cache));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    /// <inheritdoc />
    public async Task<string> CreateRefreshTokenAsync(Guid userId, CancellationToken ct = default)
    {
        // Generate secure random token
        var randomBytes = RandomNumberGenerator.GetBytes(64);
        var token = Base64UrlEncoder.Encode(randomBytes);

        var record = new RefreshTokenRecord
        {
            Token = token,
            UserId = userId,
            ExpiryDate = DateTimeOffset.UtcNow.Add(DefaultRefreshTokenLifetime),
            IsRevoked = false
        };

        var key = $"rt:{token}";
        var json = JsonSerializer.Serialize(record);

        var options = new DistributedCacheEntryOptions
        {
            AbsoluteExpirationRelativeToNow = DefaultRefreshTokenLifetime
        };

        await _cache.SetStringAsync(key, json, options, ct);
        _logger.LogDebug("Stored refresh token for user {UserId}", userId);

        return token;
    }

    /// <inheritdoc />
    public async Task<RefreshTokenRecord?> GetRefreshTokenAsync(string token, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(token))
        {
            return null;
        }

        var key = $"rt:{token}";
        var json = await _cache.GetStringAsync(key, ct);
        
        if (string.IsNullOrEmpty(json))
        {
            return null;
        }

        return JsonSerializer.Deserialize<RefreshTokenRecord>(json);
    }

    /// <inheritdoc />
    public async Task RevokeRefreshTokenAsync(string token, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(token))
        {
            return;
        }

        var record = await GetRefreshTokenAsync(token, ct);
        if (record is null)
        {
            return;
        }

        record.IsRevoked = true;

        // Save updated revocation state back to the cache
        var key = $"rt:{token}";
        var json = JsonSerializer.Serialize(record);
        
        // Calculate remaining TTL so we don't accidentally extend a revoked token's lifetime
        var timeToLive = record.ExpiryDate - DateTimeOffset.UtcNow;
        if (timeToLive > TimeSpan.Zero)
        {
            var options = new DistributedCacheEntryOptions
            {
                AbsoluteExpirationRelativeToNow = timeToLive
            };
            await _cache.SetStringAsync(key, json, options, ct);
            _logger.LogDebug("Revoked refresh token for user {UserId}", record.UserId);
        }
    }
}