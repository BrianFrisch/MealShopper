namespace MealShopper.Users.Models.DTOs;

public class UserPreferencesDto
{
    public Guid UserId { get; set; }
    public string? DefaultAddressLabel { get; set; }
    public decimal Latitude { get; set;}
    public decimal Longitude { get; set;}
    public int SearchRadiusMiles { get; set; }
    public int MaxStores { get; set; }
    public int HouseholdSize { get; set; }
    public int TargetMealCount { get; set; }
    public List<string> PreferredCuisines { get; set;} = [];
    public List<string> DietaryRestrictions { get; set;} = [];
    public List<string> AvoidIngredients { get; set;} = [];
    public DateTimeOffset? CreatedAt { get; set;}
    public DateTimeOffset? UpdatedAt { get; set;}
}