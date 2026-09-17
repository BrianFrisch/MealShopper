using MealShopper.Identity.Services;

var builder = WebApplication.CreateBuilder(args);

// Add services to the container.
// Learn more about configuring Swagger/OpenAPI at https://aka.ms/aspnetcore/swashbuckle
builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();
builder.Services.AddHttpClient();

// Register RSA key material service for JWT signing and JWKS generation
builder.Services.AddSingleton<IKeyMaterialService, RsaKeyMaterialService>();

// Register user storage and password hashing services
var redisConnection = builder.Configuration.GetConnectionString("Redis");

if (!string.IsNullOrEmpty(redisConnection))
{
    // Distributed cluster mode: AWS ElastiCache, Azure Cache for Redis, GCP Memorystore
    builder.Services.AddStackExchangeRedisCache(options =>
    {
        options.Configuration = redisConnection;
        options.InstanceName = "MealShopperIdentity:";
    });
}
else
{
    // Fallback: Local in-memory implementation of IDistributedCache for fast unit runs
    builder.Services.AddDistributedMemoryCache();
}

builder.Services.AddHttpClient<IUserStore, HttpUserStore>();
builder.Services.AddSingleton<IPasswordHasher, PasswordHasher>();
// builder.Services.AddSingleton<IUserStore, InMemoryUserStore>();
builder.Services.AddSingleton<IClientStore, InMemoryClientStore>();

// Register refresh token store
//builder.Services.AddSingleton<IRefreshTokenStore, InMemoryRefreshTokenStore>();
builder.Services.AddSingleton<IRefreshTokenStore, DistributedCacheRefreshTokenStore>();

// Register JWT token generation service
builder.Services.AddScoped<ITokenService, JwtTokenService>();

var app = builder.Build();

// Configure the HTTP request pipeline.
if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseHttpsRedirection();

app.UseAuthorization();

app.MapControllers();

app.Run();
