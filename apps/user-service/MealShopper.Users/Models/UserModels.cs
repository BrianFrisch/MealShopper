namespace MealShopper.Users.Models;

public class DbUser
{
    public Guid Id { get; set; }
    public string Email { get; set; } = string.Empty;
    public string PasswordHash { get; set; } = string.Empty;
    public string[] Roles { get; set; } = [];
    public int FailedAttempts { get; set; }
    public DateTimeOffset? LockoutUntil { get; set; }
}

public class UserPreferencesDto
{
    public Guid UserId { get; set; }
    public string Street { get; set; } = string.Empty;
    public string City { get; set; } = string.Empty;
    public string State { get; set; } = string.Empty;
    public string ZipCode { get; set; } = string.Empty;
    public int SearchRadiusMiles { get; set; } = 5;
    public int MaxStores { get; set; } = 2;
    public List<string> PreferredCuisines { get; set; } = [];
    public List<string> AvoidIngredients { get; set; } = [];
}