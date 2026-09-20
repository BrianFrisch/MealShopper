using MealShopper.Users.Data;
using MealShopper.Users.Models;
using MealShopper.Users.Services;
using Dapper;

var builder = WebApplication.CreateBuilder(args);

DefaultTypeMap.MatchNamesWithUnderscores = true;

builder.Services.AddSingleton<UserRepository>();
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
    try 
    {
        var existing = await repo.GetUserByEmailAsync(testEmail);
        if (existing == null)
        {
            await repo.CreateUserAsync(
                Guid.Parse("a51bce73-5b3e-4aad-b80c-dda90554aff2"),
                testEmail,
                hasher.HashPassword("P@ssword123!"),
                ["User"],
                new UserPreferencesDto
                {
                    Street = "123 Hawthorne Blvd",
                    City = "Lawndale",
                    State = "CA",
                    ZipCode = "90260",
                    SearchRadiusMiles = 5,
                    MaxStores = 2,
                    PreferredCuisines = ["Mexican", "American"],
                    AvoidIngredients = ["peanuts"]
                });
        }
    }
    catch (Exception ex)
    {
        app.Logger.LogWarning(ex, "Could not seed default user. Ensure Postgres and stored procedures exist.");
    }
}

if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.MapControllers();
app.Run();
