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

        if (!TryParsePasswordHash(passwordHash, out var salt, out var iterations, out var expectedHash))
        {
            return false;
        }

        var actualHash = ComputeHash(password, salt, iterations, expectedHash.Length);
        return CryptographicOperations.FixedTimeEquals(actualHash, expectedHash);
    }

    private static bool TryParsePasswordHash(
        string passwordHash,
        out byte[] salt,
        out int iterations,
        out byte[] expectedHash)
    {
        if (passwordHash.Contains(':'))
        {
            return TryParseColonFormat(passwordHash, out salt, out iterations, out expectedHash);
        }

        if (passwordHash.Contains('.'))
        {
            return TryParseDotFormat(passwordHash, out salt, out iterations, out expectedHash);
        }

        salt = [];
        iterations = 0;
        expectedHash = [];
        return false;
    }

    private static bool TryParseColonFormat(
        string passwordHash,
        out byte[] salt,
        out int iterations,
        out byte[] expectedHash)
    {
        salt = [];
        iterations = 0;
        expectedHash = [];

        // Format: {salt_base64}:{iterations}:{hash_base64}
        var parts = passwordHash.Split(':', 3);
        if (parts.Length != 3 || !int.TryParse(parts[1], out iterations))
        {
            return false;
        }

        return TryDecodeBase64Pair(parts[0], parts[2], out salt, out expectedHash);
    }

    private static bool TryParseDotFormat(
        string passwordHash,
        out byte[] salt,
        out int iterations,
        out byte[] expectedHash)
    {
        salt = [];
        iterations = 0;
        expectedHash = [];

        // Format: {iterations}.{salt_base64}.{hash_base64}
        var parts = passwordHash.Split('.', 3);
        if (parts.Length != 3 || !int.TryParse(parts[0], out iterations))
        {
            return false;
        }

        return TryDecodeBase64Pair(parts[1], parts[2], out salt, out expectedHash);
    }

    private static bool TryDecodeBase64Pair(
        string saltBase64,
        string hashBase64,
        out byte[] salt,
        out byte[] hash)
    {
        try
        {
            salt = Convert.FromBase64String(saltBase64);
            hash = Convert.FromBase64String(hashBase64);
            return true;
        }
        catch (FormatException)
        {
            salt = [];
            hash = [];
            return false;
        }
    }

    private static byte[] ComputeHash(string password, byte[] salt, int iterations, int numBytesRequested)
    {
        return KeyDerivation.Pbkdf2(
            password: password,
            salt: salt,
            prf: Prf,
            iterationCount: iterations,
            numBytesRequested: numBytesRequested);
    }
}
