using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.Filters;
using Microsoft.Extensions.DependencyInjection;

namespace MealShopper.Common.Security;

[AttributeUsage(AttributeTargets.Class | AttributeTargets.Method, AllowMultiple = false, Inherited = true)]
public class RequireGatewayUserAttribute : Attribute, IAsyncActionFilter
{
    private readonly string[] _requiredRoles;

    public RequireGatewayUserAttribute(params string[] requiredRoles)
    {
        _requiredRoles = requiredRoles ?? [];
    }

    public string Roles
    {
        get => string.Join(",", _requiredRoles);
        init => _requiredRoles = value?.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries) ?? [];
    }

    public async Task OnActionExecutionAsync(ActionExecutingContext context, ActionExecutionDelegate next)
    {
        var headers = context.HttpContext.Request.Headers;

        // 1. Authentication Check (Identity Presence)
        if (!headers.TryGetValue("X-User-Id", out var userIdStr) ||
            !Guid.TryParse(userIdStr.FirstOrDefault(), out var userId))
        {
            context.Result = new UnauthorizedResult();
            return;
        }

        // Parse claims
        var email = headers["X-User-Email"].FirstOrDefault() ?? string.Empty;
        var incomingRoles = (headers["X-User-Roles"].FirstOrDefault() ?? string.Empty)
            .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);

        // 2. Authorization Check (Role Verification)
        if (_requiredRoles.Length > 0)
        {
            var hasMatchingRole = _requiredRoles.Any(required =>
                incomingRoles.Contains(required, StringComparer.OrdinalIgnoreCase));

            if (!hasMatchingRole)
            {
                context.Result = new StatusCodeResult(StatusCodes.Status403Forbidden);
                return;
            }
        }

        // 3. Populate Injected Request Context
        var userContext = context.HttpContext.RequestServices.GetRequiredService<GatewayUserContext>();
        userContext.UserId = userId;
        userContext.Email = email;
        userContext.Roles = incomingRoles;

        await next();
    }
}