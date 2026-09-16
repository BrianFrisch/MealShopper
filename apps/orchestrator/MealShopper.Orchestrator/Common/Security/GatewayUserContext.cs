namespace MealShopper.Orchestrator.Common.Security;

/// <summary>
/// Provides user identity and role context forwarded from the API Gateway.
/// </summary>
public interface IGatewayUserContext
{
    /// <summary>
    /// Authenticated user identifier (sub).
    /// </summary>
    string? UserId { get; }

    /// <summary>
    /// User email address.
    /// </summary>
    string? Email { get; }

    /// <summary>
    /// List of authorization roles assigned to the user.
    /// </summary>
    IReadOnlyList<string> Roles { get; }

    /// <summary>
    /// Indicates whether the caller was authenticated by the API Gateway.
    /// </summary>
    bool IsAuthenticated { get; }
}

/// <summary>
/// Resolves authenticated user context from incoming HTTP headers forwarded by the API Gateway.
/// </summary>
public class GatewayUserContext : IGatewayUserContext
{
    public string? UserId { get; }
    public string? Email { get; }
    public IReadOnlyList<string> Roles { get; }
    public bool IsAuthenticated { get; }

    public GatewayUserContext(IHttpContextAccessor httpContextAccessor)
    {
        var headers = httpContextAccessor.HttpContext?.Request.Headers;

        if (headers == null)
        {
            Roles = Array.Empty<string>();
            return;
        }

        if (headers.TryGetValue("X-User-Id", out var userIdVal))
        {
            UserId = userIdVal.ToString();
        }

        if (headers.TryGetValue("X-User-Email", out var emailVal))
        {
            Email = emailVal.ToString();
        }

        if (headers.TryGetValue("X-User-Roles", out var rolesVal))
        {
            Roles = rolesVal.ToString()
                .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        }
        else
        {
            Roles = Array.Empty<string>();
        }

        if (headers.TryGetValue("X-Authenticated", out var authVal) &&
            bool.TryParse(authVal.ToString(), out var isAuth))
        {
            IsAuthenticated = isAuth;
        }
    }
}
