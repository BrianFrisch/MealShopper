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

# Install system dependencies including psql client
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*


WORKDIR /app
COPY --from=build /app/publish .

# Copy migration scripts and entrypoint into the final image
COPY ["apps/user-service/MealShopper.Users/Infrastructure/postgres", "/app/Infrastructure/postgres"]
COPY ["apps/user-service/MealShopper.Users/entrypoint.sh", "/app/entrypoint.sh"]

ENV ASPNETCORE_URLS=http://+:5125 \
    DOTNET_RUNNING_IN_CONTAINER=true

    # Grant execution permissions
RUN chmod +x /app/Infrastructure/postgres/deploy.sh /app/entrypoint.sh

EXPOSE 5125
ENTRYPOINT ["/app/entrypoint.sh"]
