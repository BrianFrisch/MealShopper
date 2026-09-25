using Dapper;
using Npgsql;
using System.Text.Json;

using MealShopper.Users.Models.DTOs;

public interface IUserPreferencesRepository
{
    Task<UserPreferencesDto?> GetPreferencesAsync(Guid userId);
    Task UpsertPreferencesAsync(Guid userId, UserPreferencesDto dto);
}

public class UserPreferencesRepository : IUserPreferencesRepository
{
    private readonly string _connectionString;

    public UserPreferencesRepository(IConfiguration configuration)
    {
        _connectionString = configuration.GetConnectionString("Postgres") ?? "";
    }

    private NpgsqlConnection CreateConnection() => new(_connectionString);

    public async Task<UserPreferencesDto?> GetPreferencesAsync(Guid userId)
    {
        using var conn = CreateConnection();
        var row = await conn.QuerySingleOrDefaultAsync(
            "SELECT * FROM fn_get_user_preferences(@UserId)",
            new { UserId = userId });

        if (row == null) return null;

        return new UserPreferencesDto
        {
            UserId = userId,
            DefaultAddressLabel = row.default_address_label,
            Latitude = row.latitude ?? 0.0M,
            Longitude = row.longitude ?? 0.0M,
            SearchRadiusMiles = row.search_radius_miles ?? 0,
            MaxStores = row.max_stores ?? 0,
            HouseholdSize = row.household_size ?? 0,
            TargetMealCount = row.target_meal_count ?? 0,
            PreferredCuisines = row.preferred_cuisines is string[] pc ? pc.ToList() : new List<string>(),
            DietaryRestrictions = row.dietary_restrictions is string[] dr ? dr.ToList() : new List<string>(),
            AvoidIngredients = row.avoid_ingredients is string[] ai ? ai.ToList() : new List<string>(),
            CreatedAt = row.created_at ?? DateTime.UtcNow,
            UpdatedAt = row.updated_at ?? DateTime.UtcNow
        };
    }
    
    public async Task UpsertPreferencesAsync(Guid userId, UserPreferencesDto dto)
    {
        using var conn = CreateConnection();
        await conn.ExecuteAsync(
            "CALL sp_upsert_user_preferences(@UserId, @AddressLabel, @Latitude, @Longitude, @SearchRadiusMiles, @MaxStores, @HouseholdSize, @TargetMealCount, @PreferredCuisines, @DietaryRestrictions, @AvoidIngredients)",
            new
            {
                UserId = userId,
                AddressLabel = dto.DefaultAddressLabel ?? string.Empty,
                Latitude = dto.Latitude,
                Longitude = dto.Longitude,
                SearchRadiusMiles = dto.SearchRadiusMiles,
                MaxStores = dto.MaxStores,
                HouseholdSize = dto.HouseholdSize,
                TargetMealCount = dto.TargetMealCount,
                PreferredCuisines = (dto.PreferredCuisines ?? new List<string>()).ToArray(),
                DietaryRestrictions = (dto.DietaryRestrictions ?? new List<string>()).ToArray(),
                AvoidIngredients = (dto.AvoidIngredients ?? new List<string>()).ToArray()
            }
        );
    }

}