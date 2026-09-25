namespace MealShopper.Users.Models.DTOs;
public class DbUser
{
    public Guid Id { get; set; }
    public string Email { get; set; } = string.Empty;
    public string PasswordHash { get; set; } = string.Empty;
    public string[] Roles { get; set; } = [];
    public int FailedAttempts { get; set; }
    public DateTimeOffset? LockoutUntil { get; set; }
}