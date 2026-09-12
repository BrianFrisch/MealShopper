using System.Net;

namespace MealShopper.Orchestrator.Exceptions;

/// <summary>
/// Exception thrown when an error occurs during communication with the Planning Domain service.
/// </summary>
public class PlanningDomainException : Exception
{
    /// <summary>
    /// HTTP status code returned by the Planning Domain service, if applicable.
    /// </summary>
    public HttpStatusCode? StatusCode { get; }

    /// <summary>
    /// Response body content returned by the Planning Domain service, if applicable.
    /// </summary>
    public string? ResponseBody { get; }

    public PlanningDomainException(string message) : base(message)
    {
    }

    public PlanningDomainException(string message, Exception innerException) : base(message, innerException)
    {
    }

    public PlanningDomainException(string message, HttpStatusCode statusCode, string? responseBody = null) 
        : base(message)
    {
        StatusCode = statusCode;
        ResponseBody = responseBody;
    }

    public PlanningDomainException(string message, HttpStatusCode statusCode, string? responseBody, Exception innerException) 
        : base(message, innerException)
    {
        StatusCode = statusCode;
        ResponseBody = responseBody;
    }
}
