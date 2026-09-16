using System.Security.Claims;

namespace MealShopper.Gateway.Middleware;

/// <summary>
/// Middleware to sanitize incoming untrusted identity headers and inject verified identity claims from the authenticated context.
/// </summary>
public class SecurityHeadersContextMiddleware
{
    private static readonly string[] HeadersToSanitize =
    [
        "X-User-Id",
        "X-User-Email",
        "X-User-Roles",
        "X-Client-Id",
        "X-Authenticated"
    ];

    private readonly RequestDelegate _next;
    private readonly ILogger<SecurityHeadersContextMiddleware> _logger;

    public SecurityHeadersContextMiddleware(RequestDelegate next, ILogger<SecurityHeadersContextMiddleware> logger)
    {
        _next = next ?? throw new ArgumentNullException(nameof(next));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    public async Task InvokeAsync(HttpContext context)
    {
        // 1. Header Sanitization: Strip untrusted client headers to prevent spoofing
        foreach (var header in HeadersToSanitize)
        {
            if (context.Request.Headers.ContainsKey(header))
            {
                context.Request.Headers.Remove(header);
            }
        }

        // 2. Context Injection: Inject trusted identity headers if the request is authenticated
        if (context.User.Identity?.IsAuthenticated == true)
        {
            var userId = context.User.FindFirst(ClaimTypes.NameIdentifier)?.Value
                         ?? context.User.FindFirst("sub")?.Value;

            if (!string.IsNullOrWhiteSpace(userId))
            {
                context.Request.Headers["X-User-Id"] = userId;
            }

            var email = context.User.FindFirst(ClaimTypes.Email)?.Value
                        ?? context.User.FindFirst("email")?.Value;

            if (!string.IsNullOrWhiteSpace(email))
            {
                context.Request.Headers["X-User-Email"] = email;
            }

            var roles = context.User.FindAll(ClaimTypes.Role)
                .Concat(context.User.FindAll("role"))
                .Select(c => c.Value)
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .ToList();

            if (roles.Count > 0)
            {
                context.Request.Headers["X-User-Roles"] = string.Join(",", roles);
            }

            var clientId = context.User.FindFirst("client_id")?.Value;
            if (!string.IsNullOrWhiteSpace(clientId))
            {
                context.Request.Headers["X-Client-Id"] = clientId;
            }

            context.Request.Headers["X-Authenticated"] = "true";
        }

        await _next(context);
    }
}

/// <summary>
/// Extension methods for registering <see cref="SecurityHeadersContextMiddleware"/>.
/// </summary>
public static class SecurityHeadersContextMiddlewareExtensions
{
    /// <summary>
    /// Adds <see cref="SecurityHeadersContextMiddleware"/> to the application request pipeline.
    /// </summary>
    public static IApplicationBuilder UseSecurityHeadersContext(this IApplicationBuilder app)
    {
        return app.UseMiddleware<SecurityHeadersContextMiddleware>();
    }
}
