namespace MealShopper.Identity.Models;

public static class TokenLifetimes
{
    public static readonly TimeSpan RefreshToken = TimeSpan.FromDays(7);
}
