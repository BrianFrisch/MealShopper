using System.Net.Http.Headers;
using System.Text;
using MealShopper.Identity.Models.DTOs;
using MealShopper.Identity.Services;
using Microsoft.AspNetCore.Mvc;

namespace MealShopper.Identity.Controllers;

[ApiController]
[Route("v1/auth")]
public class TokenController : ControllerBase
{
    private readonly IUserStore _userStore;
    private readonly IPasswordHasher _passwordHasher;
    private readonly ITokenService _tokenService;
    private readonly IRefreshTokenStore _refreshTokenStore;
    private readonly IClientStore _clientStore;
    private readonly ILogger<TokenController> _logger;

    public TokenController(
        IUserStore userStore,
        IPasswordHasher passwordHasher,
        ITokenService tokenService,
        IRefreshTokenStore refreshTokenStore,
        IClientStore clientStore,
        ILogger<TokenController> logger)
    {
        _userStore = userStore ?? throw new ArgumentNullException(nameof(userStore));
        _passwordHasher = passwordHasher ?? throw new ArgumentNullException(nameof(passwordHasher));
        _tokenService = tokenService ?? throw new ArgumentNullException(nameof(tokenService));
        _refreshTokenStore = refreshTokenStore ?? throw new ArgumentNullException(nameof(refreshTokenStore));
        _clientStore = clientStore ?? throw new ArgumentNullException(nameof(clientStore));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
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
        TokenRequest? request = formRequest;

        // Fallback: If form binding was empty or content-type is JSON, bind from body
        if (request == null || string.IsNullOrWhiteSpace(request.GrantType))
        {
            if (Request.HasJsonContentType())
            {
                request = await Request.ReadFromJsonAsync<TokenRequest>(cancellationToken: ct);
            }
        }

        if (request == null || string.IsNullOrWhiteSpace(request.GrantType))
        {
            return BadRequest(new { error = "invalid_request", error_description = "grant_type is required." });
        }

        // Check for HTTP Basic Auth header
        string? headerClientId = null;
        string? headerClientSecret = null;

        if (Request.Headers.TryGetValue("Authorization", out var authHeaderValues))
        {
            var authHeader = authHeaderValues.ToString();
            if (AuthenticationHeaderValue.TryParse(authHeader, out var parsedHeader) &&
                string.Equals(parsedHeader.Scheme, "Basic", StringComparison.OrdinalIgnoreCase) &&
                !string.IsNullOrWhiteSpace(parsedHeader.Parameter))
            {
                try
                {
                    var credentialsBytes = Convert.FromBase64String(parsedHeader.Parameter);
                    var credentials = Encoding.UTF8.GetString(credentialsBytes);
                    var colonIndex = credentials.IndexOf(':');
                    if (colonIndex >= 0)
                    {
                        headerClientId = credentials.Substring(0, colonIndex);
                        headerClientSecret = credentials.Substring(colonIndex + 1);
                    }
                }
                catch (FormatException)
                {
                    // Ignore malformed Basic auth header and fall back to request body parameters
                }
            }
        }

        // Case 1: grant_type == "client_credentials"
        if (string.Equals(request.GrantType, "client_credentials", StringComparison.OrdinalIgnoreCase))
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

            // Determine granted scopes
            List<string> grantedScopes;

            if (!string.IsNullOrWhiteSpace(request.Scope))
            {
                var requestedScopes = request.Scope
                    .Split([' ', ','], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                    .ToList();

                var unauthorizedScopes = requestedScopes
                    .Where(s => !client.AllowedScopes.Contains(s, StringComparer.OrdinalIgnoreCase))
                    .ToList();

                if (unauthorizedScopes.Count > 0)
                {
                    _logger.LogWarning(
                        "Client {ClientId} requested unauthorized scopes: {UnauthorizedScopes}",
                        clientId,
                        string.Join(", ", unauthorizedScopes));

                    return BadRequest(new { error = "invalid_scope", error_description = "One or more requested scopes are not allowed." });
                }

                grantedScopes = requestedScopes;
            }
            else
            {
                grantedScopes = client.AllowedScopes;
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

        // Case 2: grant_type == "password"
        if (string.Equals(request.GrantType, "password", StringComparison.OrdinalIgnoreCase))
        {
            if (string.IsNullOrWhiteSpace(request.Email) || string.IsNullOrWhiteSpace(request.Password))
            {
                return BadRequest(new { error = "invalid_grant", error_description = "Invalid email or password." });
            }

            var user = await _userStore.FindByEmailAsync(request.Email, ct);
            if (user == null || !_passwordHasher.VerifyPassword(request.Password, user.PasswordHash))
            {
                _logger.LogWarning("Failed authentication attempt for email: {Email}", request.Email);
                return BadRequest(new { error = "invalid_grant", error_description = "Invalid email or password." });
            }

            var scopes = new[] { "shopper.read", "planner.generate" };
            var tokenResult = await _tokenService.CreateAccessTokenAsync(
                user.Id.ToString(),
                user.Email,
                user.Roles,
                scopes: scopes,
                ct: ct);

            var refreshToken = await _refreshTokenStore.CreateRefreshTokenAsync(user.Id, ct);

            _logger.LogInformation("Successfully issued tokens for user {UserId} via password grant.", user.Id);

            var response = new TokenResponse
            {
                AccessToken = tokenResult.AccessToken,
                TokenType = tokenResult.TokenType,
                ExpiresIn = tokenResult.ExpiresIn,
                RefreshToken = refreshToken
            };

            return Ok(response);
        }

        // Case 3: grant_type == "refresh_token"
        if (string.Equals(request.GrantType, "refresh_token", StringComparison.OrdinalIgnoreCase))
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

            var scopes = new[] { "shopper.read", "planner.generate" };
            var tokenResult = await _tokenService.CreateAccessTokenAsync(
                tokenRecord.UserId.ToString(),
                string.Empty,
                ["User"],
                scopes: scopes,
                ct: ct);

            _logger.LogInformation("Successfully rotated refresh token and issued new access token for user {UserId}.", tokenRecord.UserId);

            var response = new TokenResponse
            {
                AccessToken = tokenResult.AccessToken,
                TokenType = tokenResult.TokenType,
                ExpiresIn = tokenResult.ExpiresIn,
                RefreshToken = newRefreshToken
            };

            return Ok(response);
        }

        // Case 4: Other grant types
        return BadRequest(new { error = "unsupported_grant_type", error_description = $"Grant type '{request.GrantType}' is not supported." });
    }
}
