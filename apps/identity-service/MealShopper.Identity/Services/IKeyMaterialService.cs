using Microsoft.IdentityModel.Tokens;

namespace MealShopper.Identity.Services;

/// <summary>
/// Service interface for asymmetric cryptographic key management, JWT signing, and JWKS publishing.
/// </summary>
public interface IKeyMaterialService
{
    /// <summary>
    /// Gets the active RSA security key used for cryptographic signing.
    /// </summary>
    RsaSecurityKey GetSigningKey();

    /// <summary>
    /// Gets the signing credentials configured with the active key and RS256 algorithm.
    /// </summary>
    SigningCredentials GetSigningCredentials();

    /// <summary>
    /// Gets the JSON Web Key Set (JWKS) containing only public key parameters.
    /// </summary>
    JsonWebKeySet GetPublicJwks();
}
