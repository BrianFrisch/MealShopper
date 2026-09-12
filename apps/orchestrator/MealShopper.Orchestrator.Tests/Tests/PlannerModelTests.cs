using System.Text.Json;
using FluentAssertions;
using MealShopper.Orchestrator.Models.Planner;
using MealShopper.Orchestrator.Models.Shopper;

namespace MealShopper.Orchestrator.Tests.Tests;

public class PlannerModelTests
{
    [Fact]
    public void GenerateMealPlanRequest_SerializesWithSnakeCaseNaming()
    {
        // Arrange
        var request = new GenerateMealPlanRequest
        {
            Cuisines = ["Italian", "Mexican"],
            AvoidIngredients = ["peanuts", "shellfish"],
            DaysCount = 4,
            TopDeals =
            [
                new DealItemDto
                {
                    DealId = "deal-1",
                    StoreId = "store-1",
                    StoreName = "Ralphs",
                    ItemName = "Chicken Breast",
                    NormalizedCategory = "Meat",
                    DealPrice = 2.99m,
                    Currency = "USD",
                    Unit = "lbs",
                    ValueScore = 9.0
                }
            ]
        };

        // Act
        var json = JsonSerializer.Serialize(request);
        using var doc = JsonDocument.Parse(json);
        var root = doc.RootElement;

        // Assert
        root.TryGetProperty("cuisines", out var cuisines).Should().BeTrue();
        cuisines.GetArrayLength().Should().Be(2);

        root.TryGetProperty("avoid_ingredients", out var avoidIngredients).Should().BeTrue();
        avoidIngredients.GetArrayLength().Should().Be(2);

        root.TryGetProperty("days_count", out var daysCount).Should().BeTrue();
        daysCount.GetInt32().Should().Be(4);

        root.TryGetProperty("top_deals", out var topDeals).Should().BeTrue();
        topDeals.GetArrayLength().Should().Be(1);
    }

    [Fact]
    public void MealPlanDraftResponse_DeserializesValidMealPlanFixture()
    {
        // Arrange
        var currentDir = new DirectoryInfo(AppContext.BaseDirectory);
        while (currentDir != null && !Directory.Exists(Path.Combine(currentDir.FullName, "libs")))
        {
            currentDir = currentDir.Parent;
        }

        var fixturePath = Path.Combine(currentDir!.FullName, "libs", "contracts", "tests", "fixtures", "valid-meal-plan.json");
        var json = File.ReadAllText(fixturePath);

        // Act
        var response = JsonSerializer.Deserialize<MealPlanDraftResponse>(json);

        // Assert
        response.Should().NotBeNull();
        response!.MealPlanId.Should().Be("plan-draft-20260908-001");
        response.Meals.Should().HaveCount(2);

        var dinner = response.Meals.FirstOrDefault(m => m.MealType == "Dinner");
        dinner.Should().NotBeNull();
        dinner!.RecipeTitle.Should().Be("Lemon Pepper Chicken");
        dinner.Description.Should().Contain("roasted asparagus");
        dinner.Instructions.Should().HaveCount(3);
        dinner.Ingredients.Should().HaveCount(4);

        var chickenIngredient = dinner.Ingredients.FirstOrDefault(i => i.Name == "Boneless Skinless Chicken Breast");
        chickenIngredient.Should().NotBeNull();
        chickenIngredient!.Quantity.Should().Be(1.5m);
        chickenIngredient.Unit.Should().Be("lbs");
        chickenIngredient.DealId.Should().Be("deal-chicken-breast-001");
        chickenIngredient.StoreName.Should().Be("Ralphs");
        chickenIngredient.DealPrice.Should().Be(2.99m);

        var oilIngredient = dinner.Ingredients.FirstOrDefault(i => i.Name == "Olive Oil");
        oilIngredient.Should().NotBeNull();
        oilIngredient!.Quantity.Should().Be(2m);
        oilIngredient.Unit.Should().Be("tbsp");
        oilIngredient.DealId.Should().BeNull();
        oilIngredient.StoreName.Should().BeNull();
        oilIngredient.DealPrice.Should().BeNull();

        response.MissingPrimaryIngredients.Should().HaveCount(2);
        var missingBeef = response.MissingPrimaryIngredients.FirstOrDefault(m => m.IngredientName.StartsWith("Ground Beef"));
        missingBeef.Should().NotBeNull();
        missingBeef!.Quantity.Should().Be(1.0m);
        missingBeef.Unit.Should().Be("lbs");
        missingBeef.AssociatedRecipeTitles.Should().ContainSingle().Which.Should().Be("Street Tacos");
    }
}
