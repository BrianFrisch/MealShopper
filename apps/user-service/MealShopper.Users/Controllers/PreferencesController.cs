using Microsoft.AspNetCore.Mvc;

using MealShopper.Users.Models.DTOs;
using MealShopper.Common.Security;

namespace MealShopper.Users.Controllers;

[ApiController]
[Route("v1/users")]
[RequireGatewayUser]
public class PreferencesController : ControllerBase
{
    private readonly UserPreferencesRepository _repo;
    private readonly IGatewayUserContext _user;

    public PreferencesController(UserPreferencesRepository repo, IGatewayUserContext user){
        _repo = repo;
        _user = user;
    }

    [HttpGet("me/preferences")]
    public async Task<IActionResult> GetPreferences()
    {
        var prefs = await _repo.GetPreferencesAsync(_user.UserId);
        return prefs != null ? Ok(prefs) : NotFound();
    }

    [HttpPut("me/preferences")]
    public async Task<IActionResult> UpdatePreferences([FromBody] UserPreferencesDto prefs)
    {
        await _repo.UpsertPreferencesAsync(_user.UserId, prefs);
        return NoContent();
    }
}