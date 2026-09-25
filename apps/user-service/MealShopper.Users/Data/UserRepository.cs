using Dapper;
using MealShopper.Users.Models.DTOs;
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
        string[] roles)
    {
        using var conn = CreateConnection();
        // Calls the stored procedure sp_create_user
        await conn.ExecuteAsync(
            "CALL sp_create_user(@Id, @Email, @Hash, @Roles, @Cuisines::jsonb, @Avoid::jsonb)",
            new
            {
                Id = id,
                Email = email,
                Hash = passwordHash,
                Roles = roles
            });
    }
}