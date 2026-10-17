using Microsoft.AspNetCore.Http;

namespace MealShopper.Identity.Services;

internal static class IssuerResolver
{
    public static string Resolve(IConfiguration configuration, HttpRequest? request)
    {
        var configuredIssuer = configuration["Identity:Issuer"] ?? configuration["Jwt:Issuer"];
        if (!string.IsNullOrWhiteSpace(configuredIssuer))
        {
            return configuredIssuer.TrimEnd('/');
        }

        if (request is null || !request.Host.HasValue)
        {
            return "http://localhost:5119";
        }

        var scheme = Environment.GetEnvironmentVariable("K_SERVICE") is not null
            ? Uri.UriSchemeHttps
            : request.Scheme;

        return $"{scheme}://{request.Host}".TrimEnd('/');
    }
}
