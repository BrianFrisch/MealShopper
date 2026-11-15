using System.Net;
using System.Text;
using FluentAssertions;
using MealShopper.Orchestrator.Exceptions;
using MealShopper.Orchestrator.Models.DTOs;
using MealShopper.Orchestrator.Services;
using MealShopper.Orchestrator.Tests.Helpers;
using Microsoft.Extensions.Logging.Abstractions;
using Moq;
using StackExchange.Redis;

namespace MealShopper.Orchestrator.Tests.Tests;

public class CensusGeocodingServiceTests
{
    private readonly Mock<IDatabase> _database = new();
    private readonly Mock<IConnectionMultiplexer> _redis = new();
    private readonly MockHttpMessageHandler _handler = new();

    public CensusGeocodingServiceTests()
    {
        _redis.Setup(r => r.GetDatabase(It.IsAny<int>(), It.IsAny<object>())).Returns(_database.Object);
        _database.Setup(db => db.StringGetAsync(It.IsAny<RedisKey>(), It.IsAny<CommandFlags>()))
            .ReturnsAsync(RedisValue.Null);
        _database.Setup(db => db.StringSetAsync(
            It.IsAny<RedisKey>(), It.IsAny<RedisValue>(), It.IsAny<TimeSpan?>(),
            It.IsAny<bool>(), It.IsAny<When>(), It.IsAny<CommandFlags>())).ReturnsAsync(true);
    }

    private CensusGeocodingService CreateService() =>
        new(new HttpClient(_handler), _redis.Object, NullLogger<CensusGeocodingService>.Instance);

    private static AddressDto Address() => new()
    {
        Street = "600 Example Blvd", City = "Salt Lake City", State = "UT", ZipCode = "84105-1234"
    };

    private static HttpResponseMessage Json(string content, HttpStatusCode status = HttpStatusCode.OK) =>
        new(status) { Content = new StringContent(content, Encoding.UTF8, "application/json") };

    [Fact]
    public async Task CensusMatch_UsesExactCoordinatesWithoutFallback()
    {
        _handler.CustomHandler = _ => Json("""{"result":{"addressMatches":[{"coordinates":{"x":-111.85,"y":40.73}}]}}""");

        var result = await CreateService().ResolveCoordinatesAsync(Address());

        result.Should().Be((40.73, -111.85));
        _handler.CapturedRequests.Should().ContainSingle();
    }

    [Fact]
    public async Task CensusNoMatch_FallsBackToFiveDigitZip()
    {
        _handler.CustomHandler = request => request.RequestUri!.Host.Contains("census.gov")
            ? Json("""{"result":{"addressMatches":[]}}""")
            : Json("""{"places":[{"latitude":"40.7372","longitude":"-111.8581","state abbreviation":"UT"}]}""");

        var result = await CreateService().ResolveCoordinatesAsync(Address());

        result.Should().Be((40.7372, -111.8581));
        _handler.CapturedRequests.Should().HaveCount(2);
        _handler.CapturedRequests[1].RequestUri!.AbsolutePath.Should().Be("/us/84105");
    }

    [Fact]
    public async Task CensusFailureAndMissingZip_FallBackToCityAndState()
    {
        _handler.CustomHandler = request =>
        {
            if (request.RequestUri!.Host.Contains("census.gov")) return Json("{}", HttpStatusCode.ServiceUnavailable);
            if (request.RequestUri.AbsolutePath == "/us/84105") return Json("{}", HttpStatusCode.NotFound);
            return Json("""{"places":[{"latitude":"40.7559","longitude":"-111.8967"}]}""");
        };

        var result = await CreateService().ResolveCoordinatesAsync(Address());

        result.Should().Be((40.7559, -111.8967));
        _handler.CapturedRequests.Should().HaveCount(3);
        Uri.UnescapeDataString(_handler.CapturedRequests[2].RequestUri!.AbsolutePath)
            .Should().Be("/us/UT/Salt Lake City");
    }

    [Fact]
    public async Task ZipInDifferentState_FallsBackToCityWithFullStateName()
    {
        _handler.CustomHandler = request =>
        {
            if (request.RequestUri!.Host.Contains("census.gov")) return Json("""{"result":{"addressMatches":[]}}""");
            if (request.RequestUri.AbsolutePath == "/us/84105")
                return Json("""{"places":[{"latitude":"33.9","longitude":"-118.3","state abbreviation":"CA"}]}""");
            return Json("""{"places":[{"latitude":"40.7559","longitude":"-111.8967"}]}""");
        };
        var address = Address();
        address.State = "Utah";

        var result = await CreateService().ResolveCoordinatesAsync(address);

        result.Should().Be((40.7559, -111.8967));
        Uri.UnescapeDataString(_handler.CapturedRequests[2].RequestUri!.AbsolutePath)
            .Should().Be("/us/UT/Salt Lake City");
    }

    [Fact]
    public async Task NoUsableMatches_ThrowsInsteadOfReturningDefault()
    {
        _handler.CustomHandler = request => request.RequestUri!.Host.Contains("census.gov")
            ? Json("""{"result":{"addressMatches":[{"coordinates":{"x":-111.85}}]}}""")
            : Json("""{"places":[{"latitude":"invalid","longitude":"-111.85"}]}""");

        var act = () => CreateService().ResolveCoordinatesAsync(Address());

        await act.Should().ThrowAsync<DomainException>().WithMessage("*Address could not be found*");
        _handler.CapturedRequests.Should().HaveCount(3);
    }

    [Fact]
    public async Task UnavailableProviders_ReportFailure()
    {
        _handler.CustomHandler = _ => Json("{}", HttpStatusCode.ServiceUnavailable);

        var act = () => CreateService().ResolveCoordinatesAsync(Address());

        await act.Should().ThrowAsync<DomainException>().WithMessage("*geocoding service was unavailable*");
        _handler.CapturedRequests.Should().HaveCount(3);
    }

    [Fact]
    public async Task CancelledRequest_DoesNotTryFallbacks()
    {
        using var cancellation = new CancellationTokenSource();
        _handler.CustomHandler = _ =>
        {
            cancellation.Cancel();
            throw new TaskCanceledException();
        };

        var act = () => CreateService().ResolveCoordinatesAsync(Address(), cancellation.Token);

        await act.Should().ThrowAsync<OperationCanceledException>();
        _handler.CapturedRequests.Should().ContainSingle();
    }

    [Fact]
    public async Task CacheKey_DistinguishesCityAndStateAndDoesNotUseLegacyEntries()
    {
        var keys = new List<string>();
        _database.Setup(db => db.StringGetAsync(It.IsAny<RedisKey>(), It.IsAny<CommandFlags>()))
            .Callback<RedisKey, CommandFlags>((key, _) => keys.Add(key.ToString()))
            .ReturnsAsync(RedisValue.Null);
        _handler.CustomHandler = _ => Json("""{"result":{"addressMatches":[{"coordinates":{"x":-111.85,"y":40.73}}]}}""");
        var address = Address();
        var service = CreateService();

        await service.ResolveCoordinatesAsync(address);
        address.City = "Another City";
        await service.ResolveCoordinatesAsync(address);

        keys.Should().HaveCount(2);
        keys[0].Should().StartWith("geo:cache:v2:");
        keys[1].Should().NotBe(keys[0]);
    }

    [Fact]
    public async Task ProvidedCoordinates_DoNotContactProviders()
    {
        var address = Address();
        address.Latitude = 40.7;
        address.Longitude = -111.8;

        var result = await CreateService().ResolveCoordinatesAsync(address);

        result.Should().Be((40.7, -111.8));
        _handler.CapturedRequests.Should().BeEmpty();
    }
}
