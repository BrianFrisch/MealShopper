namespace MealShopper.Orchestrator.Exceptions;

/// <summary>
/// Domain exception thrown when business logic validation fails in orchestration workflows.
/// </summary>
public class DomainException : Exception
{
    public DomainException(string message) : base(message)
    {
    }

    public DomainException(string message, Exception innerException) : base(message, innerException)
    {
    }
}
