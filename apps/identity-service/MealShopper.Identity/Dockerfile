FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

COPY ["MealShopper.Identity.csproj", "./"]
RUN dotnet restore "./MealShopper.Identity.csproj"

COPY . .
RUN dotnet publish "./MealShopper.Identity.csproj" -c Release -o /app/publish /p:UseAppHost=false

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS final
WORKDIR /app
COPY --from=build /app/publish .

ENV ASPNETCORE_URLS=http://+:5119 \
    DOTNET_RUNNING_IN_CONTAINER=true

EXPOSE 5119
ENTRYPOINT ["dotnet", "MealShopper.Identity.dll"]
