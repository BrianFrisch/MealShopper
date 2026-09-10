using System.Net;

namespace MealShopper.Orchestrator.Exceptions;

/// <summary>
/// Exception thrown when an error occurs during communication with the Shopper Domain service.
/// </summary>
public class ShopperDomainException : Exception
{
    /// <summary>
    /// HTTP status code returned by the Shopper Domain service, if applicable.
    /// </summary>
    public HttpStatusCode? StatusCode { get; }

    /// <summary>
    /// Response body content returned by the Shopper Domain service, if applicable.
    /// </summary>
    public string? ResponseBody { get; }

    public ShopperDomainException(string message) : base(message)
    {
    }

    public ShopperDomainException(string message, Exception innerException) : base(message, innerException)
    {
    }

    public ShopperDomainException(string message, HttpStatusCode statusCode, string? responseBody = null) 
        : base(message)
    {
        StatusCode = statusCode;
        ResponseBody = responseBody;
    }

    public ShopperDomainException(string message, HttpStatusCode statusCode, string? responseBody, Exception innerException) 
        : base(message, innerException)
    {
        StatusCode = statusCode;
        ResponseBody = responseBody;
    }
}
