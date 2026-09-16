using System.Security.Cryptography;
using Microsoft.AspNetCore.Cryptography.KeyDerivation;

namespace MealShopper.Identity.Services;

/// <summary>
/// Implements secure password hashing using PBKDF2 (KeyDerivation.Pbkdf2 with HMAC-SHA256, 100,000 iterations, 128-bit salt).
/// </summary>
public class PasswordHasher : IPasswordHasher
{
    private const int SaltSize = 16; // 128 bits
    private const int KeySize = 32;  // 256 bits (32 bytes)
    private const int Iterations = 100_000;
    private const KeyDerivationPrf Prf = KeyDerivationPrf.HMACSHA256;

    /// <inheritdoc />
    public string HashPassword(string password)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(password);

        var salt = RandomNumberGenerator.GetBytes(SaltSize);
        var hash = KeyDerivation.Pbkdf2(
            password: password,
            salt: salt,
            prf: Prf,
            iterationCount: Iterations,
            numBytesRequested: KeySize);

        // Format: {salt_base64}:{iterations}:{hash_base64}
        return $"{Convert.ToBase64String(salt)}:{Iterations}:{Convert.ToBase64String(hash)}";
    }

    /// <inheritdoc />
    public bool VerifyPassword(string password, string passwordHash)
    {
        if (string.IsNullOrWhiteSpace(password) || string.IsNullOrWhiteSpace(passwordHash))
        {
            return false;
        }

        // Support both delimiter formats ({salt}:{iterations}:{hash} or {iterations}.{salt}.{hash})
        string[] parts;
        byte[] salt;
        int iterations;
        byte[] expectedHash;

        if (passwordHash.Contains(':'))
        {
            parts = passwordHash.Split(':', 3);
            if (parts.Length != 3 || !int.TryParse(parts[1], out iterations))
            {
                return false;
            }

            try
            {
                salt = Convert.FromBase64String(parts[0]);
                expectedHash = Convert.FromBase64String(parts[2]);
            }
            catch (FormatException)
            {
                return false;
            }
        }
        else if (passwordHash.Contains('.'))
        {
            parts = passwordHash.Split('.', 3);
            if (parts.Length != 3 || !int.TryParse(parts[0], out iterations))
            {
                return false;
            }

            try
            {
                salt = Convert.FromBase64String(parts[1]);
                expectedHash = Convert.FromBase64String(parts[2]);
            }
            catch (FormatException)
            {
                return false;
            }
        }
        else
        {
            return false;
        }

        var actualHash = KeyDerivation.Pbkdf2(
            password: password,
            salt: salt,
            prf: Prf,
            iterationCount: iterations,
            numBytesRequested: expectedHash.Length);

        return CryptographicOperations.FixedTimeEquals(actualHash, expectedHash);
    }
}
