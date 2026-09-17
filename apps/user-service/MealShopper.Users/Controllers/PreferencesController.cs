using MealShopper.Users.Data;
using Microsoft.AspNetCore.Mvc;

namespace MealShopper.Users.Controllers;

[ApiController]
[Route("v1/users")]
public class PreferencesController : ControllerBase
{
    private readonly UserRepository _repo;

    public PreferencesController(UserRepository repo) => _repo = repo;

    [HttpGet("me/preferences")]
    public async Task<IActionResult> GetPreferences()
    {
        if (!Request.Headers.TryGetValue("X-User-Id", out var userIdStr) || !Guid.TryParse(userIdStr, out var userId))
        {
            return Unauthorized();
        }

        var prefs = await _repo.GetPreferencesAsync(userId);
        return prefs != null ? Ok(prefs) : NotFound();
    }
}