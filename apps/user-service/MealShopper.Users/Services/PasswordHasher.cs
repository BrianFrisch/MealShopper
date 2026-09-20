using System.Security.Cryptography;
using Microsoft.AspNetCore.Cryptography.KeyDerivation;

namespace MealShopper.Users.Services;

public class PasswordHasher
{
    private const int SaltByteSize = 16;
    private const int SubkeyByteSize = 32;
    private const int IterationCount = 100000;
    private const byte FormatMarker = 0x01;

    public string HashPassword(string password)
    {
        byte[] salt = RandomNumberGenerator.GetBytes(SaltByteSize);
        byte[] subkey = KeyDerivation.Pbkdf2(
            password,
            salt,
            KeyDerivationPrf.HMACSHA256,
            iterationCount: IterationCount,
            numBytesRequested: SubkeyByteSize);

        var output = new byte[1 + SaltByteSize + SubkeyByteSize]; // 49 bytes
        output[0] = FormatMarker;
        Buffer.BlockCopy(salt, 0, output, 1, SaltByteSize);
        Buffer.BlockCopy(subkey, 0, output, 1 + SaltByteSize, SubkeyByteSize);

        return Convert.ToBase64String(output);
    }

    public bool VerifyPassword(string password, string hashedPassword)
    {
        if (string.IsNullOrWhiteSpace(hashedPassword)) return false;

        byte[] decoded;
        try
        {
            decoded = Convert.FromBase64String(hashedPassword);
        }
        catch (FormatException)
        {
            return false;
        }

        if (decoded.Length != 1 + SaltByteSize + SubkeyByteSize || decoded[0] != FormatMarker)
        {
            return false;
        }

        var salt = new byte[SaltByteSize];
        Buffer.BlockCopy(decoded, 1, salt, 0, SaltByteSize);

        var expectedKey = new byte[SubkeyByteSize];
        Buffer.BlockCopy(decoded, 1 + SaltByteSize, expectedKey, 0, SubkeyByteSize);

        var actualKey = KeyDerivation.Pbkdf2(
            password,
            salt,
            KeyDerivationPrf.HMACSHA256,
            iterationCount: IterationCount,
            numBytesRequested: SubkeyByteSize);

        return CryptographicOperations.FixedTimeEquals(actualKey, expectedKey);
    }
}