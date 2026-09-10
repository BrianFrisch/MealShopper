using MealShopper.Orchestrator.Clients;
using MealShopper.Orchestrator.Services;

var builder = WebApplication.CreateBuilder(args);

// Add services to the container.
builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

// Register typed HTTP clients
builder.Services.AddHttpClient<IShopperClient, ShopperClient>(client =>
{
    client.BaseAddress = new Uri(builder.Configuration["Services:ShopperDomainUrl"] ?? "http://localhost:8001/");
});

// Register job state tracking services
builder.Services.AddSingleton<InMemoryJobTracker>();
builder.Services.AddSingleton<IJobStateStore>(sp => sp.GetRequiredService<InMemoryJobTracker>());
builder.Services.AddSingleton<IJobTracker>(sp => sp.GetRequiredService<InMemoryJobTracker>());

// Register workflow orchestrator
builder.Services.AddTransient<IMealPlanOrchestrator, MealPlanOrchestrator>();

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
