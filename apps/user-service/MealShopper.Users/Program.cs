using MealShopper.Users.Data;
using MealShopper.Users.Services;
using Dapper;

var builder = WebApplication.CreateBuilder(args);

DefaultTypeMap.MatchNamesWithUnderscores = true;

builder.Services.AddSingleton<UserRepository>();
builder.Services.AddSingleton<UserPreferencesRepository>();
builder.Services.AddSingleton<PasswordHasher>();
builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

var app = builder.Build();

// Seed test user via stored procedure on boot
using (var scope = app.Services.CreateScope())
{
    var repo = scope.ServiceProvider.GetRequiredService<UserRepository>();
    var hasher = scope.ServiceProvider.GetRequiredService<PasswordHasher>();

    var testEmail = "testuser@mealshopper.local";
    const int maxRetries = 10;

    for (var attempt = 1; attempt <= maxRetries; attempt++)
    {
        try 
        {
            var existing = await repo.GetUserByEmailAsync(testEmail);
            if (existing == null)
            {
                await repo.CreateUserAsync(
                    Guid.Parse("a51bce73-5b3e-4aad-b80c-dda90554aff2"),
                    testEmail,
                    hasher.HashPassword("P@ssword123!"),
                    ["User"]);
            }
            app.Logger.LogInformation("Database seed check completed successfully on attempt {Attempt}.", attempt);
            break;
        }
        catch (Exception ex)
        {
            app.Logger.LogWarning(ex, "Could not seed default user. Ensure Postgres and stored procedures exist.");
        }
    }
}

if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.MapControllers();
app.Run();
