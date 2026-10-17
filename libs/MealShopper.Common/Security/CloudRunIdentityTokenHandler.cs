using System.Net.Http.Headers;

namespace MealShopper.Common.Security;

public sealed class CloudRunIdentityTokenHandler : DelegatingHandler
{
    protected override async Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        if (request.RequestUri is { IsAbsoluteUri: true } destination)
        {
            var token = await CloudRunIdentityToken.GetAsync(
                destination,
                cancellationToken);

            if (token is not null)
            {
                CloudRunIdentityToken.AddInvokerAuthorization(request.Headers, token);
            }
        }

        return await base.SendAsync(request, cancellationToken);
    }
}

public static class CloudRunIdentityToken
{
    private static readonly HttpClient MetadataClient = new();

    public static bool AddInvokerAuthorization(HttpRequestHeaders headers, string token)
    {
        ArgumentNullException.ThrowIfNull(headers);
        ArgumentException.ThrowIfNullOrWhiteSpace(token);

        headers.Remove("X-Serverless-Authorization");
        return headers.TryAddWithoutValidation(
            "X-Serverless-Authorization",
            $"Bearer {token}");
    }

    public static async Task<string?> GetAsync(Uri destination, CancellationToken cancellationToken)
    {
        if (!destination.Host.EndsWith(".run.app", StringComparison.OrdinalIgnoreCase))
        {
            return null;
        }

        var audience = destination.GetLeftPart(UriPartial.Authority);
        var metadataUri = new Uri(
            "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity" +
            $"?audience={Uri.EscapeDataString(audience)}&format=full");

        using var request = new HttpRequestMessage(HttpMethod.Get, metadataUri);
        request.Headers.Add("Metadata-Flavor", "Google");

        using var response = await MetadataClient.SendAsync(request, cancellationToken);
        response.EnsureSuccessStatusCode();
        var token = (await response.Content.ReadAsStringAsync(cancellationToken)).Trim();
        if (token.Length == 0)
        {
            throw new InvalidOperationException("Cloud Run metadata server returned an empty identity token.");
        }

        return token;
    }
}
