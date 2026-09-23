// using System.Net.Http.Json;

// namespace MealShopper.Identity.Services;

// public class UserServiceClient : IUserServiceClient
// {
//     private readonly HttpClient _http;
//     private readonly ILogger<UserServiceClient> _logger;

//     public UserServiceClient(HttpClient http, ILogger<UserServiceClient> logger)
//     {
//         _http = http;
//         _logger = logger;
//     }

//     private record ValidateRequest(string Email, string Password);

//     public async Task<ValidateCredentialsResult> ValidateCredentialsAsync(
//         string email,
//         string password,
//         CancellationToken ct = default)
//     {
//         try
//         {
//             var response = await _http.PostAsJsonAsync(
//                 "/v1/internal/users/validate-credentials",
//                 new ValidateRequest(email, password),
//                 ct);

//             if (!response.IsSuccessStatusCode)
//             {
//                 _logger.LogWarning("User service credential validation returned status {Status}", response.StatusCode);
//                 return new ValidateCredentialsResult(false, Guid.Empty, string.Empty, []);
//             }

//             var result = await response.Content.ReadFromJsonAsync<ValidateCredentialsResult>(cancellationToken: ct);
//             return result ?? new ValidateCredentialsResult(false, Guid.Empty, string.Empty, []);
//         }
//         catch (Exception ex)
//         {
//             _logger.LogError(ex, "HTTP call to User Service failed during credential validation.");
//             return new ValidateCredentialsResult(false, Guid.Empty, string.Empty, []);
//         }
//     }
// }