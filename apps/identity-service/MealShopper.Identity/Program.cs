using MealShopper.Identity.Services;

var builder = WebApplication.CreateBuilder(args);

// Add services to the container.
// Learn more about configuring Swagger/OpenAPI at https://aka.ms/aspnetcore/swashbuckle
builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

// Register RSA key material service for JWT signing and JWKS generation
builder.Services.AddSingleton<IKeyMaterialService, RsaKeyMaterialService>();

// Register user storage and password hashing services
builder.Services.AddSingleton<IPasswordHasher, PasswordHasher>();
builder.Services.AddSingleton<IUserStore, InMemoryUserStore>();
builder.Services.AddSingleton<IClientStore, InMemoryClientStore>();

// Register refresh token store
builder.Services.AddSingleton<IRefreshTokenStore, InMemoryRefreshTokenStore>();

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
