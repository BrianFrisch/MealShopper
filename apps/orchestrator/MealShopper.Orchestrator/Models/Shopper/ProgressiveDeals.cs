using System.Text.Json.Serialization;

namespace MealShopper.Orchestrator.Models.Shopper;

/// <summary>Cache state and primary deals for a store.</summary>
public sealed record ProgressiveStoreDeals(
    [property: JsonPropertyName("store_id")] string StoreId,
    [property: JsonPropertyName("status")] string Status,
    [property: JsonPropertyName("deals")] List<DealItemDto> Deals);

/// <summary>Cache results for discovered stores.</summary>
public sealed record ProgressiveCacheResponse(
    [property: JsonPropertyName("stores")] List<ProgressiveStoreDeals> Stores);

/// <summary>Deals loaded for one store.</summary>
public sealed record ProgressiveLoadResponse(
    [property: JsonPropertyName("store_id")] string StoreId,
    [property: JsonPropertyName("deals")] List<DealItemDto> Deals);
