using System.Collections.Concurrent;
using MealShopper.Identity.Models;

namespace MealShopper.Identity.Services;

/// <summary>
/// Thread-safe in-memory implementation of <see cref="IClientStore"/> pre-seeded with service clients.
/// </summary>
public class InMemoryClientStore : IClientStore
{
    private readonly ConcurrentDictionary<string, ClientApplication> _clients = new(StringComparer.OrdinalIgnoreCase);
    private readonly IPasswordHasher _passwordHasher;

    public InMemoryClientStore(IPasswordHasher passwordHasher)
    {
        _passwordHasher = passwordHasher ?? throw new ArgumentNullException(nameof(passwordHasher));

        // Seed 1: orchestrator-client
        var orchestratorClient = new ClientApplication
        {
            ClientId = "orchestrator-client",
            ClientSecretHash = _passwordHasher.HashPassword("OrchestratorSecretKey_99!"),
            ClientName = "MealShopper Orchestrator Service",
            AllowedScopes = ["shopper.read", "shopper.write", "planner.generate"],
            IsActive = true,
            CreatedAt = DateTimeOffset.UtcNow
        };

        // Seed 2: shopper-client
        var shopperClient = new ClientApplication
        {
            ClientId = "shopper-client",
            ClientSecretHash = _passwordHasher.HashPassword("ShopperServiceSecretKey_88!"),
            ClientName = "MealShopper Shopper Service",
            AllowedScopes = ["shopper.read"],
            IsActive = true,
            CreatedAt = DateTimeOffset.UtcNow
        };

        _clients[orchestratorClient.ClientId] = orchestratorClient;
        _clients[shopperClient.ClientId] = shopperClient;
    }

    /// <inheritdoc />
    public Task<ClientApplication?> FindClientByIdAsync(string clientId, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(clientId))
        {
            return Task.FromResult<ClientApplication?>(null);
        }

        _clients.TryGetValue(clientId, out var client);
        return Task.FromResult(client);
    }

    /// <inheritdoc />
    public Task<bool> ValidateClientCredentialsAsync(string clientId, string clientSecret, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(clientId) || string.IsNullOrWhiteSpace(clientSecret))
        {
            return Task.FromResult(false);
        }

        if (!_clients.TryGetValue(clientId, out var client) || !client.IsActive)
        {
            return Task.FromResult(false);
        }

        var isValid = _passwordHasher.VerifyPassword(clientSecret, client.ClientSecretHash);
        return Task.FromResult(isValid);
    }
}
