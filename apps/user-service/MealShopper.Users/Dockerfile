FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

COPY ["MealShopper.Users.csproj", "./"]
RUN dotnet restore "./MealShopper.Users.csproj"

COPY . .
RUN dotnet publish "./MealShopper.Users.csproj" -c Release -o /app/publish /p:UseAppHost=false

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS final
WORKDIR /app
COPY --from=build /app/publish .

ENV ASPNETCORE_URLS=http://+:5125 \
    DOTNET_RUNNING_IN_CONTAINER=true

EXPOSE 5125
ENTRYPOINT ["dotnet", "MealShopper.Users.dll"]
