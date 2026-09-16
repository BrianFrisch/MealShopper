using System.Net.Http.Headers;
using Microsoft.Extensions.Logging;

namespace MealShopper.Orchestrator.Infrastructure.Security;

/// <summary>
/// DelegatingHandler that acquires and attaches machine-to-machine (M2M) bearer tokens to outgoing HTTP requests.
/// </summary>
public class M2MAuthenticationHandler : DelegatingHandler
{
    private readonly ITokenAcquisitionService _tokenService;
    private readonly string _requiredScope;
    private readonly ILogger<M2MAuthenticationHandler> _logger;

    public M2MAuthenticationHandler(
        ITokenAcquisitionService tokenService,
        string requiredScope,
        ILogger<M2MAuthenticationHandler> logger)
    {
        _tokenService = tokenService ?? throw new ArgumentNullException(nameof(tokenService));
        _requiredScope = requiredScope ?? throw new ArgumentNullException(nameof(requiredScope));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    /// <inheritdoc />
    protected override async Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        try
        {
            var token = await _tokenService.GetAccessTokenAsync(_requiredScope, cancellationToken);
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to acquire or attach M2M bearer token for scope '{Scope}'.", _requiredScope);
            throw;
        }

        return await base.SendAsync(request, cancellationToken);
    }
}
