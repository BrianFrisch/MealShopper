using FluentAssertions;
using MealShopper.Orchestrator.Clients;
using MealShopper.Orchestrator.Models.Domain;
using MealShopper.Orchestrator.Models.Shopper;
using MealShopper.Orchestrator.Services;
using Moq;

namespace MealShopper.Orchestrator.Tests.Tests;

public class ProgressiveDiscoveryServiceTests
{
    [Fact]
    public async Task CachedAndLoadedDealsUseTheSamePerStoreDeduplication()
    {
        var store = new StoreDto { Id = "store-1", Name = "Store" };
        var deals = new List<DealItemDto>
        {
            new() { DealId = "expensive", ItemName = "Chicken", CleanName = "chicken", DealPrice = 4 },
            new() { DealId = "cheap", ItemName = "Chicken", CleanName = "chicken", DealPrice = 2 }
        };
        var shopper = new Mock<IShopperClient>();
        shopper.Setup(s => s.GetProgressiveCacheAsync(It.IsAny<IReadOnlyList<string>>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(new ProgressiveCacheResponse([new ProgressiveStoreDeals("store-1", "cached", deals)]));
        shopper.Setup(s => s.LoadProgressiveStoreAsync("store-1", It.IsAny<CancellationToken>()))
            .ReturnsAsync(new ProgressiveLoadResponse("store-1", deals));
        var service = new ProgressiveDiscoveryService(shopper.Object);

        var cached = await service.GetCacheAsync([store], CancellationToken.None);
        var loaded = await service.LoadAsync(store, CancellationToken.None);

        cached.Stores[0].Deals.Should().ContainSingle()
            .Which.Should().Match<DealItemDto>(d => d.DealId == "cheap" && d.StoreId == "store-1" && d.StoreName == "Store");
        loaded.Deals.Should().BeEquivalentTo(cached.Stores[0].Deals);
    }

    [Fact]
    public async Task CacheRejectsMissingStoreStatuses()
    {
        var shopper = new Mock<IShopperClient>();
        shopper.Setup(s => s.GetProgressiveCacheAsync(It.IsAny<IReadOnlyList<string>>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(new ProgressiveCacheResponse([]));
        var service = new ProgressiveDiscoveryService(shopper.Object);

        var act = () => service.GetCacheAsync([new StoreDto { Id = "store-1" }], CancellationToken.None);

        await act.Should().ThrowAsync<InvalidOperationException>();
    }
}
