using MealShopper.Identity.Models;

namespace MealShopper.Identity.Services;
public class HttpUserStore : IUserStore
{
    private readonly HttpClient _http;

    public HttpUserStore(HttpClient http) => _http = http;

    public Task<ApplicationUser?> FindByEmailAsync(string email, CancellationToken ct = default)
    {
        // TokenController handles password verification by validating via User Service
        return Task.FromResult<ApplicationUser?>(null); 
    }

    public Task<ApplicationUser> CreateUserAsync(string email, string password, List<string> roles, CancellationToken ct = default)
    {
        throw new NotSupportedException("User creation delegated to MealShopper.Users service.");
    }
}