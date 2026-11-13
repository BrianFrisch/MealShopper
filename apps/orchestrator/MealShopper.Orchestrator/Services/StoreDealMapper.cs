using MealShopper.Orchestrator.Models.Domain;
using MealShopper.Orchestrator.Models.Shopper;

namespace MealShopper.Orchestrator.Services;

internal static class StoreDealMapper
{
    public static List<DealItemDto> Map(StoreDto store, IEnumerable<DealItemDto> deals) =>
        deals
            .GroupBy(d => !string.IsNullOrWhiteSpace(d.CleanName)
                ? d.CleanName.Trim().ToLowerInvariant()
                : d.ItemName.Trim().ToLowerInvariant())
            .Where(g => !string.IsNullOrWhiteSpace(g.Key))
            .Select(g =>
            {
                var best = g.OrderBy(d => d.DealPrice).ThenByDescending(d => d.ValueScore).First();
                return new DealItemDto
                {
                    DealId = best.DealId,
                    StoreId = store.Id,
                    StoreName = store.Name,
                    ItemName = best.ItemName,
                    CleanName = best.CleanName,
                    NormalizedCategory = best.NormalizedCategory,
                    PrimaryIngredient = best.PrimaryIngredient,
                    ProteinSubtype = best.ProteinSubtype,
                    ImageUrl = best.ImageUrl,
                    DealPrice = best.DealPrice,
                    OriginalPrice = best.OriginalPrice,
                    Currency = best.Currency,
                    Unit = best.Unit,
                    ValueScore = best.ValueScore
                };
            }).ToList();
}
