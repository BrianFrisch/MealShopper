using System.ComponentModel.DataAnnotations;
using MealShopper.Users.Data;
using MealShopper.Users.Services;
using Microsoft.AspNetCore.Mvc;

namespace MealShopper.Users.Controllers;

[ApiController]
[Route("v1/internal/users")]
public sealed class InternalUsersController : ControllerBase
{
    private readonly UserRepository _userRepo;
    private readonly PasswordHasher _hasher;

    public InternalUsersController(UserRepository userRepo, PasswordHasher hasher)
    {
        _userRepo = userRepo;
        _hasher = hasher;
    }

    /// <summary>Creates a user account with the standard user role.</summary>
    /// <param name="request">The email address and password for the new account.</param>
    /// <param name="cancellationToken">A token to cancel the operation.</param>
    /// <returns>The newly created user's ID and email address.</returns>
    [HttpPost]
    [ProducesResponseType(typeof(CreateUserResponse), StatusCodes.Status201Created)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status409Conflict)]
    public async Task<ActionResult<CreateUserResponse>> CreateUser(
        [FromBody] CreateUserRequest request,
        CancellationToken cancellationToken)
    {
        if (await _userRepo.GetUserByEmailAsync(request.Email, cancellationToken) is not null)
        {
            return Conflict(new ProblemDetails
            {
                Status = StatusCodes.Status409Conflict,
                Title = "Email already registered"
            });
        }

        var userId = Guid.NewGuid();
        var passwordHash = _hasher.HashPassword(request.Password);
        var created = await _userRepo.CreateUserAsync(
            userId,
            request.Email,
            passwordHash,
            ["User"],
            cancellationToken);

        if (!created)
        {
            return Conflict(new ProblemDetails
            {
                Status = StatusCodes.Status409Conflict,
                Title = "Email already registered"
            });
        }

        var response = new CreateUserResponse(userId, request.Email);
        return Created($"/v1/internal/users/{userId}", response);
    }

    /// <summary>Request payload for creating a user account.</summary>
    public sealed record CreateUserRequest
    {
        /// <summary>The user's email address.</summary>
        [Required, EmailAddress, StringLength(256)]
        public required string Email { get; init; }

        /// <summary>The user's plain-text password.</summary>
        [Required]
        public required string Password { get; init; }
    }

    /// <summary>Response containing the newly created user's public identity.</summary>
    public sealed record CreateUserResponse(Guid Id, string Email);
}
