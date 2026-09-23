FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

COPY ["MealShopper.Gateway.csproj", "./"]
RUN dotnet restore "./MealShopper.Gateway.csproj"

COPY . .
RUN dotnet publish "./MealShopper.Gateway.csproj" -c Release -o /app/publish /p:UseAppHost=false

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS final
WORKDIR /app
COPY --from=build /app/publish .

ENV ASPNETCORE_URLS=http://+:5247 \
    DOTNET_RUNNING_IN_CONTAINER=true

EXPOSE 5247
ENTRYPOINT ["dotnet", "MealShopper.Gateway.dll"]
