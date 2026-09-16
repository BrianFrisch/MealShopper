using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using MealShopper.Identity.Models;
using Microsoft.IdentityModel.Tokens;

namespace MealShopper.Identity.Services;

/// <summary>
/// JWT token service generating RS256-signed tokens using key material from <see cref="IKeyMaterialService"/>.
/// </summary>
public class JwtTokenService : ITokenService
{
    private static readonly TimeSpan DefaultTokenLifetime = TimeSpan.FromMinutes(15);
    private readonly IKeyMaterialService _keyMaterialService;
    private readonly IConfiguration _configuration;
    private readonly JwtSecurityTokenHandler _tokenHandler;

    public JwtTokenService(IKeyMaterialService keyMaterialService, IConfiguration configuration)
    {
        _keyMaterialService = keyMaterialService ?? throw new ArgumentNullException(nameof(keyMaterialService));
        _configuration = configuration ?? throw new ArgumentNullException(nameof(configuration));
        _tokenHandler = new JwtSecurityTokenHandler();
    }

    /// <inheritdoc />
    public Task<TokenResult> CreateAccessTokenAsync(
        string subject,
        string email,
        IEnumerable<string> roles,
        IEnumerable<string> scopes,
        CancellationToken ct = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(subject);

        var issuer = _configuration["Identity:Issuer"] ?? _configuration["Jwt:Issuer"] ?? "http://localhost:5119";
        var audience = _configuration["Identity:Audience"] ?? _configuration["Jwt:Audience"] ?? "mealshopper-api";
        var signingCredentials = _keyMaterialService.GetSigningCredentials();

        var claims = new List<Claim>
        {
            new(JwtRegisteredClaimNames.Sub, subject),
            new(JwtRegisteredClaimNames.Jti, Guid.NewGuid().ToString())
        };

        if (!string.IsNullOrWhiteSpace(email))
        {
            claims.Add(new Claim(JwtRegisteredClaimNames.Email, email));
        }

        if (roles != null)
        {
            foreach (var role in roles.Where(r => !string.IsNullOrWhiteSpace(r)))
            {
                claims.Add(new Claim(ClaimTypes.Role, role));
            }
        }

        if (scopes != null)
        {
            foreach (var scope in scopes.Where(s => !string.IsNullOrWhiteSpace(s)))
            {
                claims.Add(new Claim("scope", scope));
            }
        }

        var now = DateTime.UtcNow;
        var expires = now.Add(DefaultTokenLifetime);

        var tokenDescriptor = new SecurityTokenDescriptor
        {
            Subject = new ClaimsIdentity(claims),
            Issuer = issuer,
            Audience = audience,
            IssuedAt = now,
            NotBefore = now,
            Expires = expires,
            SigningCredentials = signingCredentials
        };

        var securityToken = _tokenHandler.CreateToken(tokenDescriptor);
        var tokenString = _tokenHandler.WriteToken(securityToken);

        var result = new TokenResult
        {
            AccessToken = tokenString,
            TokenType = "Bearer",
            ExpiresIn = (int)DefaultTokenLifetime.TotalSeconds,
            RefreshToken = null
        };

        return Task.FromResult(result);
    }

    /// <inheritdoc />
    public Task<TokenResult> CreateClientTokenAsync(
        string clientId,
        IEnumerable<string> authorizedScopes,
        CancellationToken ct = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(clientId);

        var issuer = _configuration["Identity:Issuer"] ?? _configuration["Jwt:Issuer"] ?? "http://localhost:5001";
        var audience = _configuration["Identity:Audience"] ?? _configuration["Jwt:Audience"] ?? "mealshopper-api";
        var signingCredentials = _keyMaterialService.GetSigningCredentials();

        var claims = new List<Claim>
        {
            new(JwtRegisteredClaimNames.Sub, clientId),
            new(JwtRegisteredClaimNames.Jti, Guid.NewGuid().ToString()),
            new("client_id", clientId)
        };

        if (authorizedScopes != null)
        {
            foreach (var scope in authorizedScopes.Where(s => !string.IsNullOrWhiteSpace(s)))
            {
                claims.Add(new Claim("scope", scope));
            }
        }

        var now = DateTime.UtcNow;
        var expires = now.Add(DefaultTokenLifetime);

        var tokenDescriptor = new SecurityTokenDescriptor
        {
            Subject = new ClaimsIdentity(claims),
            Issuer = issuer,
            Audience = audience,
            IssuedAt = now,
            NotBefore = now,
            Expires = expires,
            SigningCredentials = signingCredentials
        };

        var securityToken = _tokenHandler.CreateToken(tokenDescriptor);
        var tokenString = _tokenHandler.WriteToken(securityToken);

        var result = new TokenResult
        {
            AccessToken = tokenString,
            TokenType = "Bearer",
            ExpiresIn = (int)DefaultTokenLifetime.TotalSeconds,
            RefreshToken = null
        };

        return Task.FromResult(result);
    }
}
