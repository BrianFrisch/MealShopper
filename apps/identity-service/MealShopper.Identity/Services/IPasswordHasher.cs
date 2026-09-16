namespace MealShopper.Identity.Services;

/// <summary>
/// Service interface for securely hashing and verifying passwords.
/// </summary>
public interface IPasswordHasher
{
    /// <summary>
    /// Generates a secure hash of the provided password using PBKDF2 with salt.
    /// </summary>
    /// <param name="password">Plain text password.</param>
    /// <returns>Formatted password hash string containing salt and hash data.</returns>
    string HashPassword(string password);

    /// <summary>
    /// Verifies that a plaintext password matches the stored password hash.
    /// </summary>
    /// <param name="password">Plain text password.</param>
    /// <param name="passwordHash">Stored password hash.</param>
    /// <returns>True if password matches; otherwise false.</returns>
    bool VerifyPassword(string password, string passwordHash);
}
