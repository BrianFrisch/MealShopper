using System.Security.Cryptography;
using Microsoft.IdentityModel.Tokens;

namespace MealShopper.Identity.Services;

/// <summary>
/// RSA implementation of <see cref="IKeyMaterialService"/> providing 2048-bit asymmetric key management for JWT signing and public JWKS generation.
/// </summary>
public class RsaKeyMaterialService : IKeyMaterialService, IDisposable
{
    private const string DefaultKeyId = "mealshopper-dev-key-1";
    private readonly RSA _rsa;
    private readonly RsaSecurityKey _signingKey;
    private readonly SigningCredentials _signingCredentials;
    private readonly JsonWebKeySet _publicJwks;
    private bool _disposed;

    public RsaKeyMaterialService(IConfiguration? configuration = null, IHostEnvironment? environment = null)
    {
        var keyId = configuration?["Jwt:KeyId"] ?? DefaultKeyId;

        // Initialize 2048-bit RSA key pair
        _rsa = RSA.Create(2048);

        _signingKey = new RsaSecurityKey(_rsa)
        {
            KeyId = keyId
        };

        _signingCredentials = new SigningCredentials(_signingKey, SecurityAlgorithms.RsaSha256);

        // Export only the public parameters (modulus and exponent) to ensure private key is never exposed
        var rsaPublicParameters = _rsa.ExportParameters(includePrivateParameters: false);

        var publicJwk = new JsonWebKey
        {
            Kty = JsonWebAlgorithmsKeyTypes.RSA,
            Use = "sig",
            Alg = SecurityAlgorithms.RsaSha256,
            Kid = keyId,
            N = Base64UrlEncoder.Encode(rsaPublicParameters.Modulus),
            E = Base64UrlEncoder.Encode(rsaPublicParameters.Exponent)
        };

        _publicJwks = new JsonWebKeySet();
        _publicJwks.Keys.Add(publicJwk);
    }

    /// <inheritdoc />
    public RsaSecurityKey GetSigningKey() => _signingKey;

    /// <inheritdoc />
    public SigningCredentials GetSigningCredentials() => _signingCredentials;

    /// <inheritdoc />
    public JsonWebKeySet GetPublicJwks() => _publicJwks;

    public void Dispose()
    {
        if (!_disposed)
        {
            _rsa.Dispose();
            _disposed = true;
        }
        GC.SuppressFinalize(this);
    }
}
