using System.Net.Http.Json;
using System.Text.Json.Serialization;
using Microsoft.Extensions.Caching.Memory;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;

namespace MealShopper.Orchestrator.Infrastructure.Security;

/// <summary>
/// Acquires OAuth2 machine-to-machine tokens using the client credentials grant and caches them in memory.
/// </summary>
public class ClientCredentialsTokenAcquisitionService : ITokenAcquisitionService
{
    private readonly HttpClient _httpClient;
    private readonly IMemoryCache _memoryCache;
    private readonly IConfiguration _configuration;
    private readonly ILogger<ClientCredentialsTokenAcquisitionService> _logger;

    public ClientCredentialsTokenAcquisitionService(
        HttpClient httpClient,
        IMemoryCache memoryCache,
        IConfiguration configuration,
        ILogger<ClientCredentialsTokenAcquisitionService> logger)
    {
        _httpClient = httpClient ?? throw new ArgumentNullException(nameof(httpClient));
        _memoryCache = memoryCache ?? throw new ArgumentNullException(nameof(memoryCache));
        _configuration = configuration ?? throw new ArgumentNullException(nameof(configuration));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    /// <inheritdoc />
    public async Task<string> GetAccessTokenAsync(string scope, CancellationToken ct = default)
    {
        var tokenEndpoint = _configuration["Identity:TokenEndpoint"] ?? "http://localhost:5119/v1/auth/token";
        var clientId = _configuration["Identity:ClientId"] ?? "orchestrator-client";
        var clientSecret = _configuration["Identity:ClientSecret"] ?? "OrchestratorSecretKey_99!";

        var cacheKey = $"m2m_token_{clientId}_{scope}";

        if (_memoryCache.TryGetValue(cacheKey, out string? cachedToken) && !string.IsNullOrWhiteSpace(cachedToken))
        {
            return cachedToken;
        }

        var requestPayload = new
        {
            grant_type = "client_credentials",
            client_id = clientId,
            client_secret = clientSecret,
            scope = scope
        };

        _logger.LogInformation(
            "Acquiring M2M access token for client {ClientId} with scope '{Scope}' from {TokenEndpoint}.",
            clientId,
            scope,
            tokenEndpoint);

        using var response = await _httpClient.PostAsJsonAsync(tokenEndpoint, requestPayload, ct);

        if (!response.IsSuccessStatusCode)
        {
            var errorBody = await response.Content.ReadAsStringAsync(ct);
            _logger.LogError(
                "Failed to acquire M2M access token from Identity Service. StatusCode: {StatusCode}, Response: {ResponseBody}",
                response.StatusCode,
                errorBody);

            throw new InvalidOperationException(
                $"Failed to acquire M2M access token: {(int)response.StatusCode} {response.StatusCode} - {errorBody}");
        }

        var tokenResponse = await response.Content.ReadFromJsonAsync<TokenResponseDto>(cancellationToken: ct);

        if (tokenResponse == null || string.IsNullOrWhiteSpace(tokenResponse.AccessToken))
        {
            throw new InvalidOperationException("Identity service returned an empty token response.");
        }

        var expiresInSeconds = tokenResponse.ExpiresIn > 0 ? tokenResponse.ExpiresIn : 900;
        var cacheDurationSeconds = Math.Max(30, expiresInSeconds - 60);

        _memoryCache.Set(cacheKey, tokenResponse.AccessToken, TimeSpan.FromSeconds(cacheDurationSeconds));

        return tokenResponse.AccessToken;
    }

    private class TokenResponseDto
    {
        [JsonPropertyName("access_token")]
        public string AccessToken { get; set; } = string.Empty;

        [JsonPropertyName("token_type")]
        public string TokenType { get; set; } = string.Empty;

        [JsonPropertyName("expires_in")]
        public int ExpiresIn { get; set; } = 900;

        [JsonPropertyName("scope")]
        public string? Scope { get; set; }
    }
}
