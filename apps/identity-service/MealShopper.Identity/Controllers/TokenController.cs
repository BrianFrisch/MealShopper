using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text;
using MealShopper.Identity.Models.DTOs;
using MealShopper.Identity.Services;
using Microsoft.AspNetCore.Mvc;

namespace MealShopper.Identity.Controllers;

[ApiController]
[Route("v1/auth")]
public class TokenController : ControllerBase
{
    private static readonly string[] DefaultUserScopes = ["shopper.read", "planner.generate"];

    private readonly ITokenService _tokenService;
    private readonly IRefreshTokenStore _refreshTokenStore;
    private readonly IClientStore _clientStore;
    private readonly HttpClient _httpClient;
    private readonly ILogger<TokenController> _logger;
    private readonly string _userServiceBaseUrl;

    private sealed record ValidateCredentialsResponse(bool IsValid, Guid UserId, string Email, List<string>? Roles);

    public TokenController(
        ITokenService tokenService,
        IRefreshTokenStore refreshTokenStore,
        IClientStore clientStore,
        ILogger<TokenController> logger,
        IConfiguration configuration,
        IHttpClientFactory? httpClientFactory = null,
        HttpClient? httpClient = null)
    {
        _tokenService = tokenService ?? throw new ArgumentNullException(nameof(tokenService));
        _refreshTokenStore = refreshTokenStore ?? throw new ArgumentNullException(nameof(refreshTokenStore));
        _clientStore = clientStore ?? throw new ArgumentNullException(nameof(clientStore));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _httpClient = httpClient ?? httpClientFactory?.CreateClient() ?? new HttpClient();

        // Resolve user service URL from environment/appsettings with localhost fallback
        _userServiceBaseUrl = configuration["UserService:BaseUrl"] 
            ?? configuration["Services:UserServiceUrl"] 
            ?? configuration["UserServiceUrl"] 
            ?? "http://localhost:5125";
            
        _userServiceBaseUrl = _userServiceBaseUrl.TrimEnd('/');
    }

    /// <summary>
    /// Issues access and refresh tokens using password, refresh_token, or client_credentials grant types.
    /// </summary>
    [HttpPost("token")]
    [Consumes("application/json", "application/x-www-form-urlencoded")]
    [Produces("application/json")]
    [ProducesResponseType(typeof(TokenResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status401Unauthorized)]
    public async Task<IActionResult> Token([FromForm] TokenRequest? formRequest, CancellationToken ct)
    {
        var request = await ResolveTokenRequestAsync(formRequest, ct);
        if (request == null || string.IsNullOrWhiteSpace(request.GrantType))
        {
            return BadRequest(new { error = "invalid_request", error_description = "grant_type is required." });
        }

        TryExtractBasicAuthCredentials(out var headerClientId, out var headerClientSecret);

        return request.GrantType.ToLowerInvariant() switch
        {
            "client_credentials" => await HandleClientCredentialsGrantAsync(request, headerClientId, headerClientSecret, ct),
            "password"           => await HandlePasswordGrantAsync(request, ct),
            "refresh_token"      => await HandleRefreshTokenGrantAsync(request, ct),
            _                    => BadRequest(new { error = "unsupported_grant_type", error_description = $"Grant type '{request.GrantType}' is not supported." })
        };
    }

    private async Task<TokenRequest?> ResolveTokenRequestAsync(TokenRequest? formRequest, CancellationToken ct)
    {
        var request = formRequest;
        if ((request == null || string.IsNullOrWhiteSpace(request.GrantType)) && Request.HasJsonContentType())
        {
            request = await Request.ReadFromJsonAsync<TokenRequest>(cancellationToken: ct);
        }

        return request;
    }

    private bool TryExtractBasicAuthCredentials(out string? clientId, out string? clientSecret)
    {
        clientId = null;
        clientSecret = null;

        if (!Request.Headers.TryGetValue("Authorization", out var authHeaderValues))
        {
            return false;
        }

        var authHeader = authHeaderValues.ToString();
        if (!AuthenticationHeaderValue.TryParse(authHeader, out var parsedHeader) ||
            !string.Equals(parsedHeader.Scheme, "Basic", StringComparison.OrdinalIgnoreCase) ||
            string.IsNullOrWhiteSpace(parsedHeader.Parameter))
        {
            return false;
        }

        try
        {
            var credentialsBytes = Convert.FromBase64String(parsedHeader.Parameter);
            var credentials = Encoding.UTF8.GetString(credentialsBytes);
            var colonIndex = credentials.IndexOf(':');
            if (colonIndex >= 0)
            {
                clientId = credentials.Substring(0, colonIndex);
                clientSecret = credentials.Substring(colonIndex + 1);
                return true;
            }
        }
        catch (FormatException)
        {
            // Ignore malformed Basic auth header and fall back to request body parameters
        }

        return false;
    }

    private async Task<IActionResult> HandleClientCredentialsGrantAsync(
        TokenRequest request,
        string? headerClientId,
        string? headerClientSecret,
        CancellationToken ct)
    {
        var clientId = headerClientId ?? request.ClientId;
        var clientSecret = headerClientSecret ?? request.ClientSecret;

        if (string.IsNullOrWhiteSpace(clientId) || string.IsNullOrWhiteSpace(clientSecret))
        {
            return BadRequest(new { error = "invalid_client", error_description = "Missing client credentials." });
        }

        var isValidClient = await _clientStore.ValidateClientCredentialsAsync(clientId, clientSecret, ct);
        if (!isValidClient)
        {
            _logger.LogWarning("Client authentication failed for client_id: {ClientId}", clientId);
            return Unauthorized(new { error = "invalid_client", error_description = "Client authentication failed." });
        }

        var client = await _clientStore.FindClientByIdAsync(clientId, ct);
        if (client == null || !client.IsActive)
        {
            return Unauthorized(new { error = "invalid_client", error_description = "Client is inactive or not found." });
        }

        if (!TryValidateScopes(client.ClientId, client.AllowedScopes, request.Scope, out var grantedScopes, out var scopeErrorResult))
        {
            return scopeErrorResult;
        }

        var tokenResult = await _tokenService.CreateClientTokenAsync(client.ClientId, grantedScopes, ct);

        _logger.LogInformation(
            "Issued machine-to-machine access token for client {ClientId} with scopes [{Scopes}].",
            client.ClientId,
            string.Join(" ", grantedScopes));

        return Ok(new
        {
            access_token = tokenResult.AccessToken,
            token_type = tokenResult.TokenType,
            expires_in = tokenResult.ExpiresIn,
            scope = string.Join(" ", grantedScopes)
        });
    }

    private bool TryValidateScopes(
        string clientId,
        List<string> allowedScopes,
        string? requestedScopeString,
        out List<string> grantedScopes,
        out IActionResult errorResult)
    {
        grantedScopes = allowedScopes;
        errorResult = null!;

        if (string.IsNullOrWhiteSpace(requestedScopeString))
        {
            return true;
        }

        var requestedScopes = requestedScopeString
            .Split([' ', ','], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .ToList();

        var unauthorizedScopes = requestedScopes
            .Where(s => !allowedScopes.Contains(s, StringComparer.OrdinalIgnoreCase))
            .ToList();

        if (unauthorizedScopes.Count > 0)
        {
            _logger.LogWarning(
                "Client {ClientId} requested unauthorized scopes: {UnauthorizedScopes}",
                clientId,
                string.Join(", ", unauthorizedScopes));

            errorResult = BadRequest(new { error = "invalid_scope", error_description = "One or more requested scopes are not allowed." });
            return false;
        }

        grantedScopes = requestedScopes;
        return true;
    }

    private async Task<IActionResult> HandlePasswordGrantAsync(TokenRequest request, CancellationToken ct)
    {
        if (string.IsNullOrWhiteSpace(request.Email) || string.IsNullOrWhiteSpace(request.Password))
        {
            return BadRequest(new { error = "invalid_grant", error_description = "Invalid email or password." });
        }

        var (validationResult, errorResponse) = await ValidateUserCredentialsAsync(request.Email, request.Password, ct);
        if (errorResponse != null)
        {
            return errorResponse;
        }

        var tokenResult = await _tokenService.CreateAccessTokenAsync(
            validationResult!.UserId.ToString(),
            validationResult.Email,
            validationResult.Roles ?? ["User"],
            scopes: DefaultUserScopes,
            ct: ct);

        var refreshToken = await _refreshTokenStore.CreateRefreshTokenAsync(validationResult.UserId, ct);

        _logger.LogInformation("Successfully issued tokens for user {UserId} via password grant.", validationResult.UserId);

        return Ok(new TokenResponse
        {
            AccessToken = tokenResult.AccessToken,
            TokenType = tokenResult.TokenType,
            ExpiresIn = tokenResult.ExpiresIn,
            RefreshToken = refreshToken
        });
    }

    private async Task<(ValidateCredentialsResponse? Result, IActionResult? Error)> ValidateUserCredentialsAsync(
        string email,
        string password,
        CancellationToken ct)
    {
        HttpResponseMessage validationResponse;
        try
        {
            validationResponse = await _httpClient.PostAsJsonAsync(
                $"{_userServiceBaseUrl}/v1/internal/users/validate-credentials",
                new { email, password },
                ct);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to reach user validation endpoint for email: {Email}", email);
            return (null, StatusCode(StatusCodes.Status503ServiceUnavailable, new { error = "temporarily_unavailable", error_description = "Authentication service unavailable." }));
        }

        if ((int)validationResponse.StatusCode == StatusCodes.Status423Locked)
        {
            _logger.LogWarning("Account locked for email: {Email}", email);
            return (null, StatusCode(StatusCodes.Status423Locked, new { error = "account_locked", error_description = "Account is locked." }));
        }

        if (!validationResponse.IsSuccessStatusCode)
        {
            _logger.LogWarning("User validation returned unsuccessful status code {StatusCode} for email: {Email}", validationResponse.StatusCode, email);
            return (null, BadRequest(new { error = "invalid_grant", error_description = "Invalid email or password." }));
        }

        var validationResult = await validationResponse.Content.ReadFromJsonAsync<ValidateCredentialsResponse>(cancellationToken: ct);
        if (validationResult == null || !validationResult.IsValid)
        {
            _logger.LogWarning("Failed authentication attempt for email: {Email}", email);
            return (null, BadRequest(new { error = "invalid_grant", error_description = "Invalid email or password." }));
        }

        return (validationResult, null);
    }

    private async Task<IActionResult> HandleRefreshTokenGrantAsync(TokenRequest request, CancellationToken ct)
    {
        if (string.IsNullOrWhiteSpace(request.RefreshToken))
        {
            return BadRequest(new { error = "invalid_grant", error_description = "Invalid or expired refresh token." });
        }

        var tokenRecord = await _refreshTokenStore.GetRefreshTokenAsync(request.RefreshToken, ct);
        if (tokenRecord == null || tokenRecord.IsRevoked || tokenRecord.ExpiryDate < DateTimeOffset.UtcNow)
        {
            _logger.LogWarning("Invalid, expired, or revoked refresh token provided.");
            return BadRequest(new { error = "invalid_grant", error_description = "Invalid or expired refresh token." });
        }

        // Single-use rotation: Revoke current refresh token
        await _refreshTokenStore.RevokeRefreshTokenAsync(request.RefreshToken, ct);

        // Issue new access token and new refresh token
        var newRefreshToken = await _refreshTokenStore.CreateRefreshTokenAsync(tokenRecord.UserId, ct);

        var tokenResult = await _tokenService.CreateAccessTokenAsync(
            tokenRecord.UserId.ToString(),
            string.Empty,
            ["User"],
            scopes: DefaultUserScopes,
            ct: ct);

        _logger.LogInformation("Successfully rotated refresh token and issued new access token for user {UserId}.", tokenRecord.UserId);

        return Ok(new TokenResponse
        {
            AccessToken = tokenResult.AccessToken,
            TokenType = tokenResult.TokenType,
            ExpiresIn = tokenResult.ExpiresIn,
            RefreshToken = newRefreshToken
        });
    }
}
