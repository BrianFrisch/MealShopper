using System.Security.Claims;
using MealShopper.Gateway.Middleware;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.IdentityModel.Tokens;

var builder = WebApplication.CreateBuilder(args);

// Add services to the container.
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

// Add YARP Reverse Proxy
builder.Services.AddReverseProxy().LoadFromConfig(builder.Configuration.GetSection("ReverseProxy"));

// Add JWT Bearer authentication services
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.Authority = builder.Configuration["Identity:Authority"];
        options.Audience = builder.Configuration["Identity:Audience"];
        options.RequireHttpsMetadata = builder.Configuration.GetValue<bool>("Identity:RequireHttpsMetadata");
        
        options.Events = new JwtBearerEvents
        {
            OnAuthenticationFailed = context =>
            {
                var logger = context.HttpContext.RequestServices.GetRequiredService<ILogger<Program>>();
                logger.LogError(context.Exception, "Authentication failed: {Message}", context.Exception.Message);
                return Task.CompletedTask;
            }
        };

        options.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuer = true,
            ValidIssuer = builder.Configuration["Identity:Authority"],
            ValidateAudience = true,
            ValidAudience = builder.Configuration["Identity:Audience"],
            ValidateIssuerSigningKey = true,
            ValidateLifetime = true,
            ClockSkew = TimeSpan.FromSeconds(30)
        };
    });

// Add authorization policies
builder.Services.AddAuthorization(options =>
{
    options.AddPolicy("AuthenticatedUser", policy =>
    {
        policy.RequireAuthenticatedUser();
    });

    options.AddPolicy("RequireShopperScope", policy =>
    {
        policy.RequireAuthenticatedUser();
        policy.RequireAssertion(context =>
            context.User.FindAll("scope").Any(c => c.Value.Split([' ', ','], StringSplitOptions.RemoveEmptyEntries).Contains("shopper.read", StringComparer.OrdinalIgnoreCase)) ||
            context.User.IsInRole("User") ||
            context.User.HasClaim(ClaimTypes.Role, "User"));
    });

    options.AddPolicy("RequirePlannerScope", policy =>
    {
        policy.RequireAuthenticatedUser();
        policy.RequireAssertion(context =>
            context.User.FindAll("scope").Any(c => c.Value.Split([' ', ','], StringSplitOptions.RemoveEmptyEntries).Contains("planner.generate", StringComparer.OrdinalIgnoreCase)) ||
            context.User.IsInRole("User") ||
            context.User.HasClaim(ClaimTypes.Role, "User"));
    });

    options.AddPolicy("MachineClient", policy =>
    {
        policy.RequireAuthenticatedUser();
        policy.RequireClaim("client_id");
    });
});

var app = builder.Build();

// Configure the HTTP request pipeline.
if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseHttpsRedirection();

app.UseRouting();

app.UseAuthentication();
app.UseSecurityHeadersContext();
app.UseAuthorization();

app.MapReverseProxy();


app.Run();
