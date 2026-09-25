using MealShopper.Users.Models.DTOs;
using Microsoft.AspNetCore.Mvc;

namespace MealShopper.Users.Controllers;

[ApiController]
[Route("v1/users")]
public class PreferencesController : ControllerBase
{
    private readonly UserPreferencesRepository _repo;

    public PreferencesController(UserPreferencesRepository repo) => _repo = repo;

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

    [HttpPut("me/preferences")]
    public async Task<IActionResult> UpdatePreferences([FromBody] UserPreferencesDto prefs)
    {
        if (!Request.Headers.TryGetValue("X-User-Id", out var userIdStr) || !Guid.TryParse(userIdStr, out var userId))
        {
            return Unauthorized();
        }

        await _repo.UpsertPreferencesAsync(userId, prefs);
        return NoContent();
    }
}