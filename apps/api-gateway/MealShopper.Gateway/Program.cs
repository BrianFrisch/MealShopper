using System.Security.Claims;
using MealShopper.Common.Security;
using MealShopper.Gateway.Middleware;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.IdentityModel.Tokens;
using Yarp.ReverseProxy.Transforms;

var builder = WebApplication.CreateBuilder(args);

// 1. Define policy name
const string AllowLocalFrontendPolicy = "AllowLocalFrontend";

// 2. Register CORS service
builder.Services.AddCors(options =>
{
    options.AddPolicy(AllowLocalFrontendPolicy, policy =>
    {
        var allowedOrigins = builder.Configuration
            .GetSection("Cors:AllowedOrigins")
            .Get<string[]>() ?? ["http://localhost:5173", "http://127.0.0.1:5173"];

        policy.WithOrigins(allowedOrigins)
            .AllowAnyHeader()
            .AllowAnyMethod()
            .AllowCredentials(); // Required if sending cookies/authorization credentials
    });
});

// Add services to the container.
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

// Add YARP Reverse Proxy
builder.Services.AddReverseProxy()
    .LoadFromConfig(builder.Configuration.GetSection("ReverseProxy"))
    .AddTransforms(transformBuilder =>
    {
        transformBuilder.AddRequestTransform(async transformContext =>
        {
            var destination = new Uri(transformContext.DestinationPrefix, UriKind.Absolute);
            var logger = transformContext.HttpContext.RequestServices
                .GetRequiredService<ILogger<Program>>();
            var token = await CloudRunIdentityToken.GetAsync(
                destination,
                transformContext.HttpContext.RequestAborted);
            if (token is null)
            {
                logger.LogWarning(
                    "No Cloud Run identity token was returned for proxy destination {Destination}.",
                    destination.GetLeftPart(UriPartial.Authority));
                return;
            }

            var headerAdded = CloudRunIdentityToken.AddInvokerAuthorization(
                    transformContext.ProxyRequest.Headers,
                    token);
            logger.LogInformation(
                "Cloud Run identity token acquired for {Destination}; invoker header added: {HeaderAdded}.",
                destination.GetLeftPart(UriPartial.Authority),
                headerAdded);
        });
    });

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

        options.BackchannelHttpHandler = new CloudRunIdentityTokenHandler
        {
            InnerHandler = new HttpClientHandler()
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

// UseCors MUST come immediately after UseRouting and before Authentication/Authorization
app.UseCors(AllowLocalFrontendPolicy);

app.UseAuthentication();
app.UseSecurityHeadersContext();
app.UseAuthorization();

app.MapReverseProxy();


app.Run();
