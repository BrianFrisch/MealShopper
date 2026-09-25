namespace MealShopper.Common.Security;

public interface IGatewayUserContext
{
    Guid UserId { get; }
    string Email { get; }
    IReadOnlyList<string> Roles { get; }
    bool IsAuthenticated { get; }
}

public class GatewayUserContext : IGatewayUserContext
{
    public Guid UserId { get; set; }
    public string Email { get; set; } = string.Empty;
    public IReadOnlyList<string> Roles { get; set; } = [];
    public bool IsAuthenticated => UserId != Guid.Empty;
}