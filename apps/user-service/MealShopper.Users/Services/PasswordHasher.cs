using System.Security.Cryptography;
using Microsoft.AspNetCore.Cryptography.KeyDerivation;

namespace MealShopper.Users.Services;

public class PasswordHasher
{
    public string HashPassword(string password)
    {
        byte[] salt = RandomNumberGenerator.GetBytes(128 / 8);
        byte[] subkey = KeyDerivation.Pbkdf2(
            password,
            salt,
            KeyDerivationPrf.HMACSHA256,
            iterationCount: 100000,
            numBytesRequested: 256 / 8);

        var output = new byte[13 + salt.Length + subkey.Length];
        output[0] = 0x01; // Format marker
        Buffer.BlockCopy(salt, 0, output, 1, salt.Length);
        Buffer.BlockCopy(subkey, 0, output, 1 + salt.Length, subkey.Length);
        return Convert.ToBase64String(output);
    }

    public bool VerifyPassword(string password, string hashedPassword)
    {
        var decoded = Convert.FromBase64String(hashedPassword);
        if (decoded.Length != 49 || decoded[0] != 0x01) return false;

        var salt = new byte[16];
        Buffer.BlockCopy(decoded, 1, salt, 0, 16);

        var expectedKey = new byte[32];
        Buffer.BlockCopy(decoded, 17, expectedKey, 0, 32);

        var actualKey = KeyDerivation.Pbkdf2(
            password,
            salt,
            KeyDerivationPrf.HMACSHA256,
            iterationCount: 100000,
            numBytesRequested: 32);

        return CryptographicOperations.FixedTimeEquals(actualKey, expectedKey);
    }
}