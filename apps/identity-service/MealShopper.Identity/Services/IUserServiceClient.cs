// namespace MealShopper.Identity.Services;

// /// <summary>
// /// Result returned from credential validation against the User Service.
// /// </summary>
// /// <param name="IsValid">Indicates whether the credentials are valid.</param>
// /// <param name="UserId">The unique identifier of the validated user.</param>
// /// <param name="Email">The user's email address.</param>
// /// <param name="Roles">The roles assigned to the user.</param>
// public record ValidateCredentialsResult(bool IsValid, Guid UserId, string Email, List<string> Roles);

// /// <summary>
// /// Client interface for communicating with the downstream User Service.
// /// </summary>
// public interface IUserServiceClient
// {
//     /// <summary>
//     /// Validates user credentials asynchronously against the User Service.
//     /// </summary>
//     /// <param name="email">The user's email address.</param>
//     /// <param name="password">The user's password.</param>
//     /// <param name="ct">Cancellation token.</param>
//     /// <returns>A <see cref="ValidateCredentialsResult"/> containing validation results and user info.</returns>
//     Task<ValidateCredentialsResult> ValidateCredentialsAsync(
//         string email,
//         string password,
//         CancellationToken ct = default);
// }
