using MealShopper.Users.Data;
using MealShopper.Users.Services;
using Microsoft.AspNetCore.Mvc;

namespace MealShopper.Users.Controllers;

[ApiController]
[Route("v1/internal/users")]
public class InternalValidationController : ControllerBase
{
    private readonly UserRepository _userRepo;
    private readonly PasswordHasher _hasher;

    public InternalValidationController(UserRepository userRepo, PasswordHasher hasher)
    {
        _userRepo = userRepo;
        _hasher = hasher;
    }

    public record ValidateCredentialsRequest(string Email, string Password);
    public record ValidateCredentialsResponse(bool IsValid, Guid UserId, string Email, List<string> Roles);

    [HttpPost("validate-credentials")]
    public async Task<IActionResult> ValidateCredentials([FromBody] ValidateCredentialsRequest request)
    {
        var user = await _userRepo.GetUserByEmailAsync(request.Email);
        if (user == null)
        {
            return Ok(new ValidateCredentialsResponse(false, Guid.Empty, string.Empty, []));
        }

        if (user.LockoutUntil.HasValue && user.LockoutUntil.Value > DateTimeOffset.UtcNow)
        {
            return StatusCode(StatusCodes.Status423Locked, new { error = "account_locked" });
        }

        if (!_hasher.VerifyPassword(request.Password, user.PasswordHash))
        {
            await _userRepo.RecordLoginFailureAsync(user.Id);
            return Ok(new ValidateCredentialsResponse(false, Guid.Empty, string.Empty, []));
        }

        await _userRepo.ResetLoginFailureAsync(user.Id);
        return Ok(new ValidateCredentialsResponse(true, user.Id, user.Email, user.Roles.ToList()));
    }
}