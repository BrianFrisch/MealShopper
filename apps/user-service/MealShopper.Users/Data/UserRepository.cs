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

    public async Task<DbUser?> GetUserByEmailAsync(
        string email,
        CancellationToken cancellationToken = default)
    {
        using var conn = CreateConnection();
        // Calls the stored function fn_get_user_by_email
        return await conn.QuerySingleOrDefaultAsync<DbUser>(
            new CommandDefinition(
                "SELECT * FROM fn_get_user_by_email(@Email)",
                new { Email = email },
                cancellationToken: cancellationToken));
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

    public async Task<bool> CreateUserAsync(
        Guid id,
        string email,
        string passwordHash,
        string[] roles,
        CancellationToken cancellationToken = default)
    {
        using var conn = CreateConnection();
        // Calls the stored procedure sp_create_user
        await conn.ExecuteAsync(
            new CommandDefinition(
                "CALL sp_create_user(@Id, @Email, @Hash, @Roles)",
                new
                {
                    Id = id,
                    Email = email,
                    Hash = passwordHash,
                    Roles = roles
                },
                cancellationToken: cancellationToken));

        var createdUser = await GetUserByEmailAsync(email, cancellationToken);
        return createdUser?.Id == id;
    }
}