using FluentAssertions;
using MealShopper.Orchestrator.Clients;
using MealShopper.Orchestrator.Exceptions;
using MealShopper.Orchestrator.Tests.Helpers;
using Microsoft.Extensions.Logging.Abstractions;

namespace MealShopper.Orchestrator.Tests.Tests;

public class ShopperClientTests
{
    private readonly MockHttpMessageHandler _mockHandler;
    private readonly ShopperClient _client;

    public ShopperClientTests()
    {
        _mockHandler = new MockHttpMessageHandler();
        var httpClient = new HttpClient(_mockHandler)
        {
            BaseAddress = new Uri("http://localhost:8001/")
        };

        _client = new ShopperClient(httpClient, NullLogger<ShopperClient>.Instance);
    }

    [Fact]
    public async Task DiscoverStoresAsync_CorrectlyDeserializesStores_FromMockHandler()
    {
        // Arrange & Act
        var stores = await _client.DiscoverStoresAsync(34.053625, -118.243007, 5, 2);

        // Assert
        stores.Should().NotBeNull();
        stores.Should().HaveCount(2);

        var firstStore = stores[0];
        firstStore.StoreId.Should().Be("store_vons_1");
        firstStore.Name.Should().Be("Vons");
        firstStore.Address.Should().Be("123 Hawthorne Blvd");
        firstStore.DistanceMiles.Should().Be(1.5);

        var secondStore = stores[1];
        secondStore.StoreId.Should().Be("store_grocoutlet_1");
        secondStore.Name.Should().Be("Grocery Outlet");
        secondStore.Address.Should().Be("456 Inglewood Ave");
        secondStore.DistanceMiles.Should().Be(2.2);
    }

    [Fact]
    public async Task GetTopDealsAsync_CorrectlyDeserializesDeals_MatchingSchemaFixture()
    {
        // Arrange
        var storeIds = new List<string> { "store-ralphs-101", "store-traderjoes-204", "store-sprouts-305" };
        var avoidIngredients = new List<string> { "peanuts" };

        // Act
        var response = await _client.GetTopDealsAsync(storeIds, avoidIngredients);

        // Assert
        response.Should().NotBeNull();
        response.RegionContext.Should().NotBeNull();
        response.RegionContext.Coordinates.Should().NotBeNull();
        response.RegionContext.StoreIds.Should().NotBeEmpty();

        response.Deals.Should().NotBeNull();
        response.Deals.Should().HaveCount(3);

        var chickenDeal = response.Deals.FirstOrDefault(d => d.DealId == "deal-chicken-breast-001");
        chickenDeal.Should().NotBeNull();
        chickenDeal!.StoreId.Should().Be("store-ralphs-101");
        chickenDeal.StoreName.Should().Be("Ralphs");
        chickenDeal.ItemName.Should().Be("Boneless Skinless Chicken Breast");
        chickenDeal.NormalizedCategory.Should().Be("Meat");
        chickenDeal.DealPrice.Should().Be(2.99m);
        chickenDeal.OriginalPrice.Should().Be(4.99m);
        chickenDeal.Currency.Should().Be("USD");
        chickenDeal.Unit.Should().Be("lb");
        chickenDeal.ValueScore.Should().Be(9.2);

        var produceDeal = response.Deals.FirstOrDefault(d => d.DealId == "deal-bell-peppers-002");
        produceDeal.Should().NotBeNull();
        produceDeal!.NormalizedCategory.Should().Be("Produce");
        produceDeal.DealPrice.Should().Be(0.99m);
        produceDeal.ValueScore.Should().Be(8.5);

        var bakeryDeal = response.Deals.FirstOrDefault(d => d.DealId == "deal-tortillas-003");
        bakeryDeal.Should().NotBeNull();
        bakeryDeal!.NormalizedCategory.Should().Be("Bakery");
        bakeryDeal.DealPrice.Should().Be(1.49m);
        bakeryDeal.ValueScore.Should().Be(7.8);
    }

    [Fact]
    public async Task DiscoverStoresAsync_ThrowsShopperDomainException_On500ServerError()
    {
        // Arrange
        _mockHandler.SetServerError("Database connection failed in Shopper Domain");

        // Act
        var act = () => _client.DiscoverStoresAsync(34.053625, -118.243007, 5, 2);

        // Assert
        var exception = await act.Should().ThrowAsync<ShopperDomainException>();
        exception.Which.StatusCode.Should().Be(System.Net.HttpStatusCode.InternalServerError);
        exception.Which.ResponseBody.Should().Contain("Database connection failed");
    }

    [Fact]
    public async Task GetTopDealsAsync_ThrowsShopperDomainException_On500ServerError()
    {
        // Arrange
        _mockHandler.SetServerError("Deals engine scoring crashed");

        // Act
        var act = () => _client.GetTopDealsAsync(new List<string> { "store-1" }, new List<string>());

        // Assert
        var exception = await act.Should().ThrowAsync<ShopperDomainException>();
        exception.Which.StatusCode.Should().Be(System.Net.HttpStatusCode.InternalServerError);
        exception.Which.ResponseBody.Should().Contain("Deals engine scoring crashed");
    }
}
