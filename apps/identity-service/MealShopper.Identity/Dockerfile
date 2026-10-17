FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

COPY ["apps/identity-service/MealShopper.Identity/MealShopper.Identity.csproj", "apps/identity-service/MealShopper.Identity/"]
COPY ["libs/MealShopper.Common/MealShopper.Common.csproj", "libs/MealShopper.Common/"]
RUN dotnet restore "apps/identity-service/MealShopper.Identity/MealShopper.Identity.csproj"

COPY ["apps/identity-service/MealShopper.Identity/", "apps/identity-service/MealShopper.Identity/"]
COPY ["libs/MealShopper.Common/", "libs/MealShopper.Common/"]

WORKDIR "/src/apps/identity-service/MealShopper.Identity"
RUN dotnet publish "MealShopper.Identity.csproj" -c Release -o /app/publish /p:UseAppHost=false

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS final
WORKDIR /app
COPY --from=build /app/publish .

ENV ASPNETCORE_URLS=http://+:5119 \
    DOTNET_RUNNING_IN_CONTAINER=true

EXPOSE 5119
ENTRYPOINT ["dotnet", "MealShopper.Identity.dll"]
