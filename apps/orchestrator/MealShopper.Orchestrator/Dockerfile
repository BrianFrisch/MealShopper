FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

# Project files caching
COPY ["apps/orchestrator/MealShopper.Orchestrator/MealShopper.Orchestrator.csproj", "apps/orchestrator/MealShopper.Orchestrator/"]
COPY ["libs/MealShopper.Common/MealShopper.Common.csproj", "libs/MealShopper.Common/"]
RUN dotnet restore "apps/orchestrator/MealShopper.Orchestrator/MealShopper.Orchestrator.csproj"

# Source copy
COPY ["apps/orchestrator/MealShopper.Orchestrator/", "apps/orchestrator/MealShopper.Orchestrator/"]
COPY ["libs/MealShopper.Common/", "libs/MealShopper.Common/"]

WORKDIR "/src/apps/orchestrator/MealShopper.Orchestrator"
RUN dotnet publish "MealShopper.Orchestrator.csproj" -c Release -o /app/publish /p:UseAppHost=false

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS final
WORKDIR /app
COPY --from=build /app/publish .

ENV ASPNETCORE_URLS=http://+:5277 \
    DOTNET_RUNNING_IN_CONTAINER=true

EXPOSE 5277
ENTRYPOINT ["dotnet", "MealShopper.Orchestrator.dll"]