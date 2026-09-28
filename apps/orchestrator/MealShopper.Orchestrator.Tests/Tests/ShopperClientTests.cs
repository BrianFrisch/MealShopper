using FluentAssertions;
using MealShopper.Orchestrator.Clients;
using MealShopper.Orchestrator.Exceptions;
using MealShopper.Orchestrator.Models.Planner;
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

    [Fact]
    public async Task LookupIngredientsAsync_ReturnsEmptyList_WhenMissingIngredientsIsEmpty()
    {
        // Act
        var result = await _client.LookupIngredientsAsync(new List<string> { "store_vons_1" }, new List<MissingIngredientDto>());

        // Assert
        result.Should().NotBeNull();
        result.Should().BeEmpty();
        _mockHandler.CapturedRequests.Should().BeEmpty();
    }

    [Fact]
    public async Task LookupIngredientsAsync_CorrectlyDeserializesMatches_FromMockHandler()
    {
        // Arrange
        var missingIngredients = new List<MissingIngredientDto>
        {
            new() { IngredientName = "Garlic", Quantity = 2, Unit = "each" },
            new() { IngredientName = "Olive Oil", Quantity = 1, Unit = "bottle" }
        };

        // Act
        var matches = await _client.LookupIngredientsAsync(new List<string> { "store_vons_1", "store_grocoutlet_1" }, missingIngredients);

        // Assert
        matches.Should().NotBeNull();
        matches.Should().NotBeEmpty();

        var garlicMatch = matches.FirstOrDefault(m => m.IngredientName == "Garlic");
        garlicMatch.Should().NotBeNull();
        garlicMatch!.DealId.Should().Be("deal-garlic-101");
        garlicMatch.StoreId.Should().Be("store_vons_1");
        garlicMatch.StoreName.Should().Be("Vons");
        garlicMatch.DealPrice.Should().Be(0.50m);
        garlicMatch.Unit.Should().Be("each");

        var oilMatch = matches.FirstOrDefault(m => m.IngredientName == "Olive Oil");
        oilMatch.Should().NotBeNull();
        oilMatch!.DealId.Should().Be("deal-oil-202");
        oilMatch.StoreId.Should().Be("store_grocoutlet_1");
        oilMatch.StoreName.Should().Be("Grocery Outlet");
        oilMatch.DealPrice.Should().Be(5.99m);
        oilMatch.Unit.Should().Be("bottle");

        var asparagusMatch = matches.FirstOrDefault(m => m.IngredientName == "Asparagus");
        asparagusMatch.Should().NotBeNull();
        asparagusMatch!.StoreName.Should().Be("Vons");
        asparagusMatch.DealPrice.Should().Be(3.99m);
    }

    [Fact]
    public async Task LookupIngredientsAsync_ThrowsShopperDomainException_On500ServerError()
    {
        // Arrange
        _mockHandler.SetServerError("Ingredient lookup service error");
        var missingIngredients = new List<MissingIngredientDto>
        {
            new() { IngredientName = "Garlic", Quantity = 2, Unit = "each" }
        };

        // Act
        var act = () => _client.LookupIngredientsAsync(new List<string> { "store_vons_1" }, missingIngredients);

        // Assert
        var exception = await act.Should().ThrowAsync<ShopperDomainException>();
        exception.Which.StatusCode.Should().Be(System.Net.HttpStatusCode.InternalServerError);
        exception.Which.ResponseBody.Should().Contain("Ingredient lookup service error");
    }

    [Fact]
    public async Task GetDealsForStoreAsync_ReturnsDeals_WhenStoreExists()
    {
        // Act
        var deals = await _client.GetDealsForStoreAsync("ralphs-101");

        // Assert
        deals.Should().NotBeNull();
        deals.Should().HaveCount(2);
        deals[0].StoreId.Should().Be("ralphs-101");
        deals[0].ItemName.Should().Be("Boneless Skinless Chicken Breast");
        deals[0].DealPrice.Should().Be(2.99m);
    }

    [Fact]
    public async Task GetDealsForStoreAsync_ReturnsEmptyList_When404NotFound()
    {
        // Arrange
        _mockHandler.SetCustomResponse(System.Net.HttpStatusCode.NotFound, "{\"detail\":\"No active deals found for store\"}");

        // Act
        var deals = await _client.GetDealsForStoreAsync("unknown-store");

        // Assert
        deals.Should().NotBeNull();
        deals.Should().BeEmpty();
    }

    [Fact]
    public async Task GetDealsForStoreAsync_ReturnsEmptyList_WhenServerError()
    {
        // Arrange
        _mockHandler.SetServerError("Shopper service down");

        // Act
        var deals = await _client.GetDealsForStoreAsync("ralphs-101");

        // Assert
        deals.Should().NotBeNull();
        deals.Should().BeEmpty();
    }

    [Fact]
    public async Task GetTopDealsForStoresAsync_FetchesConcurrentlyAndDeduplicatesBestPrice()
    {
        // Arrange
        _mockHandler.CustomHandler = request =>
        {
            var url = request.RequestUri?.ToString() ?? "";
            if (url.Contains("ralphs-101"))
            {
                var json = """
                {
                  "timestamp": "2026-09-27T10:00:00Z",
                  "region_context": { "coordinates": { "latitude": 33.8895, "longitude": -118.3533 }, "store_ids": ["ralphs-101"] },
                  "deals": [
                    { "deal_id": "r1", "store_id": "ralphs-101", "store_name": "Ralphs", "item_name": "Honeycrisp Apples", "clean_name": "honeycrisp apples", "deal_price": 1.99, "value_score": 8.0, "unit": "lb" }
                  ]
                }
                """;
                return new HttpResponseMessage(System.Net.HttpStatusCode.OK) { Content = new StringContent(json, System.Text.Encoding.UTF8, "application/json") };
            }
            if (url.Contains("aldi-202"))
            {
                var json = """
                {
                  "timestamp": "2026-09-27T10:00:00Z",
                  "region_context": { "coordinates": { "latitude": 33.8895, "longitude": -118.3533 }, "store_ids": ["aldi-202"] },
                  "deals": [
                    { "deal_id": "a1", "store_id": "aldi-202", "store_name": "ALDI", "item_name": "Honeycrisp Apples", "clean_name": "honeycrisp apples", "deal_price": 1.29, "value_score": 9.5, "unit": "lb" },
                    { "deal_id": "a2", "store_id": "aldi-202", "store_name": "ALDI", "item_name": "Whole Milk", "clean_name": "whole milk", "deal_price": 2.79, "value_score": 8.5, "unit": "each" }
                  ]
                }
                """;
                return new HttpResponseMessage(System.Net.HttpStatusCode.OK) { Content = new StringContent(json, System.Text.Encoding.UTF8, "application/json") };
            }
            return null;
        };

        // Act
        var result = await _client.GetTopDealsForStoresAsync(["ralphs-101", "aldi-202"]);

        // Assert
        result.Should().NotBeNull();
        result.RegionContext.StoreIds.Should().Contain(["ralphs-101", "aldi-202"]);
        result.Deals.Should().HaveCount(2);

        // Deduplication by clean_name should keep ALDI's Honeycrisp Apples ($1.29) over Ralphs ($1.99)
        var appleDeal = result.Deals.FirstOrDefault(d => d.CleanName == "honeycrisp apples");
        appleDeal.Should().NotBeNull();
        appleDeal!.DealId.Should().Be("a1");
        appleDeal.DealPrice.Should().Be(1.29m);
        appleDeal.StoreId.Should().Be("aldi-202");

        // Ordered by value_score descending
        result.Deals[0].ValueScore.Should().BeGreaterThanOrEqualTo(result.Deals[1].ValueScore);
    }

    [Fact]
    public async Task GetTopDealsForStoresAsync_ReturnsEmptyDeals_WhenStoreIdsEmpty()
    {
        // Act
        var result = await _client.GetTopDealsForStoresAsync(new List<string>());

        // Assert
        result.Should().NotBeNull();
        result.Deals.Should().BeEmpty();
        result.RegionContext.StoreIds.Should().BeEmpty();
    }
}
