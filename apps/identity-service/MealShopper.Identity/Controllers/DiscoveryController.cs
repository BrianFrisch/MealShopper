using Microsoft.AspNetCore.Mvc;
using Microsoft.IdentityModel.Tokens;
using MealShopper.Identity.Services;

namespace MealShopper.Identity.Controllers;

[ApiController]
public class DiscoveryController : ControllerBase
{
    private readonly IKeyMaterialService _keyMaterialService;
    private readonly IConfiguration _configuration;
    private readonly ILogger<DiscoveryController> _logger;

    public DiscoveryController(
        IKeyMaterialService keyMaterialService,
        IConfiguration configuration,
        ILogger<DiscoveryController> logger)
    {
        _keyMaterialService = keyMaterialService ?? throw new ArgumentNullException(nameof(keyMaterialService));
        _configuration = configuration ?? throw new ArgumentNullException(nameof(configuration));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    /// <summary>
    /// Returns OpenID Connect discovery metadata.
    /// </summary>
    [HttpGet(".well-known/openid-configuration")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    public IActionResult GetConfiguration()
    {
        var baseUrl = (_configuration["Jwt:Issuer"] ?? $"{Request.Scheme}://{Request.Host}").TrimEnd('/');

        var config = new
        {
            issuer = baseUrl,
            jwks_uri = $"{baseUrl}/.well-known/jwks.json",
            token_endpoint = $"{baseUrl}/v1/auth/token",
            userinfo_endpoint = $"{baseUrl}/v1/auth/userinfo",
            response_types_supported = new[] { "token", "id_token" },
            subject_types_supported = new[] { "public" },
            id_token_signing_alg_values_supported = new[] { "RS256" },
            scopes_supported = new[]
            {
                "openid",
                "profile",
                "email",
                "shopper.read",
                "planner.generate",
                "offline_access"
            },
            token_endpoint_auth_methods_supported = new[]
            {
                "client_secret_post",
                "client_secret_basic"
            }
        };

        _logger.LogInformation("Returning OpenID Connect configuration for issuer: {Issuer}", baseUrl);

        return Ok(config);
    }

    /// <summary>
    /// Returns the JSON Web Key Set (JWKS) containing the public keys for signature verification.
    /// </summary>
    [HttpGet(".well-known/jwks.json")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    public IActionResult GetJwks()
    {
        var jwks = _keyMaterialService.GetPublicJwks();
        return Ok(jwks);
    }
}
