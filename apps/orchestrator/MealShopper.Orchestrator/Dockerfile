FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

COPY ["MealShopper.Orchestrator.csproj", "./"]
RUN dotnet restore "./MealShopper.Orchestrator.csproj"

COPY . .
RUN dotnet publish "./MealShopper.Orchestrator.csproj" -c Release -o /app/publish /p:UseAppHost=false

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS final
WORKDIR /app
COPY --from=build /app/publish .

ENV ASPNETCORE_URLS=http://+:5277 \
    DOTNET_RUNNING_IN_CONTAINER=true

EXPOSE 5277
ENTRYPOINT ["dotnet", "MealShopper.Orchestrator.dll"]