FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

COPY ["apps/api-gateway/MealShopper.Gateway/MealShopper.Gateway.csproj", "apps/api-gateway/MealShopper.Gateway/"]
COPY ["libs/MealShopper.Common/MealShopper.Common.csproj", "libs/MealShopper.Common/"]
RUN dotnet restore "apps/api-gateway/MealShopper.Gateway/MealShopper.Gateway.csproj"

COPY ["apps/api-gateway/MealShopper.Gateway/", "apps/api-gateway/MealShopper.Gateway/"]
COPY ["libs/MealShopper.Common/", "libs/MealShopper.Common/"]

WORKDIR "/src/apps/api-gateway/MealShopper.Gateway"
RUN dotnet publish "MealShopper.Gateway.csproj" -c Release -o /app/publish /p:UseAppHost=false

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS final
WORKDIR /app
COPY --from=build /app/publish .

ENV ASPNETCORE_URLS=http://+:5247 \
    DOTNET_RUNNING_IN_CONTAINER=true

EXPOSE 5247
ENTRYPOINT ["dotnet", "MealShopper.Gateway.dll"]
