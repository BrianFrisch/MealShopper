using System.Data;
using System.Text.Json;
using Dapper;
using MealShopper.Users.Models;
using Npgsql;

namespace MealShopper.Users.Data;

public class UserRepository
{
    private readonly string _connectionString;

    public UserRepository(IConfiguration configuration)
    {
        _connectionString = configuration.GetConnectionString("Postgres") ?? "";
    }

    private NpgsqlConnection CreateConnection() => new(_connectionString);

    public async Task<DbUser?> GetUserByEmailAsync(string email)
    {
        using var conn = CreateConnection();
        // Calls the stored function fn_get_user_by_email
        return await conn.QuerySingleOrDefaultAsync<DbUser>(
            "SELECT * FROM fn_get_user_by_email(@Email)",
            new { Email = email });
    }

    public async Task RecordLoginFailureAsync(Guid userId, int maxAttempts = 5, int lockoutMinutes = 15)
    {
        using var conn = CreateConnection();
        // Calls the stored procedure sp_record_login_failure
        await conn.ExecuteAsync(
            "CALL sp_record_login_failure(@UserId, @MaxAttempts, @LockoutMinutes)",
            new { UserId = userId, MaxAttempts = maxAttempts, LockoutMinutes = lockoutMinutes });
    }

    public async Task ResetLoginFailureAsync(Guid userId)
    {
        using var conn = CreateConnection();
        // Calls the stored procedure sp_reset_login_failure
        await conn.ExecuteAsync(
            "CALL sp_reset_login_failure(@UserId)",
            new { UserId = userId });
    }

    public async Task CreateUserAsync(
        Guid id,
        string email,
        string passwordHash,
        string[] roles,
        UserPreferencesDto prefs)
    {
        using var conn = CreateConnection();
        // Calls the stored procedure sp_create_user
        await conn.ExecuteAsync(
            "CALL sp_create_user(@Id, @Email, @Hash, @Roles, @Street, @City, @State, @Zip, @Cuisines::jsonb, @Avoid::jsonb)",
            new
            {
                Id = id,
                Email = email,
                Hash = passwordHash,
                Roles = roles,
                Street = prefs.Street,
                City = prefs.City,
                State = prefs.State,
                Zip = prefs.ZipCode,
                Cuisines = JsonSerializer.Serialize(prefs.PreferredCuisines),
                Avoid = JsonSerializer.Serialize(prefs.AvoidIngredients)
            });
    }

    public async Task<UserPreferencesDto?> GetPreferencesAsync(Guid userId)
    {
        using var conn = CreateConnection();
        // Calls the stored function fn_get_user_preferences
        var row = await conn.QuerySingleOrDefaultAsync(
            "SELECT * FROM fn_get_user_preferences(@UserId)",
            new { UserId = userId });

        if (row == null) return null;

        return new UserPreferencesDto
        {
            UserId = row.user_id,
            Street = row.street,
            City = row.city,
            State = row.state,
            ZipCode = row.zip_code,
            SearchRadiusMiles = row.search_radius_miles,
            MaxStores = row.max_stores,

            // PreferredCuisines = JsonSerializer.Deserialize<List<string>>(row.preferred_cuisines ?? "[]") ?? [],
            // AvoidIngredients = JsonSerializer.Deserialize<List<string>>(row.avoid_ingredients ?? "[]") ?? []
            PreferredCuisines = JsonSerializer.Deserialize<List<string>>((string?)row.preferred_cuisines ?? "[]") ?? [],
            AvoidIngredients = JsonSerializer.Deserialize<List<string>>((string?)row.avoid_ingredients ?? "[]") ?? []
        };
    }
}