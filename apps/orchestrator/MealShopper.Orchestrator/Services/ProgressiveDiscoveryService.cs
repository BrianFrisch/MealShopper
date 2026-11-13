using MealShopper.Orchestrator.Clients;
using MealShopper.Orchestrator.Models.Domain;
using MealShopper.Orchestrator.Models.Shopper;

namespace MealShopper.Orchestrator.Services;

public interface IProgressiveDiscoveryService
{
    Task<ProgressiveCacheResponse> GetCacheAsync(List<StoreDto> stores, CancellationToken ct);
    Task<ProgressiveLoadResponse> LoadAsync(StoreDto store, CancellationToken ct);
}

public sealed class ProgressiveDiscoveryService(IShopperClient shopper) : IProgressiveDiscoveryService
{
    public async Task<ProgressiveCacheResponse> GetCacheAsync(List<StoreDto> stores, CancellationToken ct)
    {
        if (stores.Count == 0) return new ProgressiveCacheResponse([]);
        var result = await shopper.GetProgressiveCacheAsync(stores.Select(s => s.Id).ToList(), ct);
        var storeById = stores.ToDictionary(s => s.Id);
        if (result.Stores.Count != stores.Count ||
            result.Stores.Select(s => s.StoreId).Distinct().Count() != stores.Count ||
            result.Stores.Any(s => !storeById.ContainsKey(s.StoreId) || s.Status is not ("cached" or "missing" or "error")))
            throw new InvalidOperationException("Shopper returned an invalid store cache response.");
        return new ProgressiveCacheResponse(result.Stores.Select(s => s with
        {
            Deals = s.Status == "cached" ? StoreDealMapper.Map(storeById[s.StoreId], s.Deals) : []
        }).ToList());
    }

    public async Task<ProgressiveLoadResponse> LoadAsync(StoreDto store, CancellationToken ct)
    {
        var result = await shopper.LoadProgressiveStoreAsync(store.Id, ct);
        if (result.StoreId != store.Id)
            throw new InvalidOperationException("Shopper returned deals for a different store.");
        return result with { Deals = StoreDealMapper.Map(store, result.Deals) };
    }
}
