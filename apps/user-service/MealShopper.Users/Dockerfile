FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

# 1. Copy project definitions for optimized layer caching
COPY ["apps/user-service/MealShopper.Users/MealShopper.Users.csproj", "apps/user-service/MealShopper.Users/"]
COPY ["libs/MealShopper.Common/MealShopper.Common.csproj", "libs/MealShopper.Common/"]
RUN dotnet restore "apps/user-service/MealShopper.Users/MealShopper.Users.csproj"

# 2. Copy only required source code trees
COPY ["apps/user-service/MealShopper.Users/", "apps/user-service/MealShopper.Users/"]
COPY ["libs/MealShopper.Common/", "libs/MealShopper.Common/"]

# 3. Publish directly to the output folder
WORKDIR "/src/apps/user-service/MealShopper.Users"
RUN dotnet publish "MealShopper.Users.csproj" -c Release -o /app/publish /p:UseAppHost=false

# 4. Final runtime image
FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS final
WORKDIR /app
COPY --from=build /app/publish .

ENV ASPNETCORE_URLS=http://+:5125 \
    DOTNET_RUNNING_IN_CONTAINER=true

EXPOSE 5125
ENTRYPOINT ["dotnet", "MealShopper.Users.dll"]
