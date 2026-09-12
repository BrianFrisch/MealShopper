using System.Net;
using FluentAssertions;
using MealShopper.Orchestrator.Clients;
using MealShopper.Orchestrator.Exceptions;
using MealShopper.Orchestrator.Models.Planner;
using MealShopper.Orchestrator.Models.Shopper;
using MealShopper.Orchestrator.Tests.Helpers;
using Microsoft.Extensions.Logging.Abstractions;

namespace MealShopper.Orchestrator.Tests.Tests;

public class PlanningClientTests
{
    private readonly MockHttpMessageHandler _mockHandler;
    private readonly PlanningClient _client;

    public PlanningClientTests()
    {
        _mockHandler = new MockHttpMessageHandler();
        var httpClient = new HttpClient(_mockHandler)
        {
            BaseAddress = new Uri("http://localhost:8002/")
        };

        _client = new PlanningClient(httpClient, NullLogger<PlanningClient>.Instance);
    }

    [Fact]
    public async Task GenerateMealPlanAsync_SendsPostToExpectedEndpoint_AndReturnsMealPlanDraft()
    {
        // Arrange
        const string mockResponseJson = """
        {
          "meal_plan_id": "plan-123",
          "meals": [
            {
              "meal_type": "Dinner",
              "recipe_title": "Lemon Chicken",
              "description": "Tasty lemon chicken",
              "instructions": ["Cook chicken", "Add lemon"],
              "ingredients": [
                {
                  "name": "Chicken Breast",
                  "quantity": 1.5,
                  "unit": "lbs",
                  "deal_id": "deal-1",
                  "store_name": "Ralphs",
                  "deal_price": 2.99
                }
              ]
            }
          ],
          "missing_primary_ingredients": [
            {
              "ingredient_name": "Olive Oil",
              "quantity": 2.0,
              "unit": "tbsp",
              "associated_recipe_titles": ["Lemon Chicken"]
            }
          ]
        }
        """;

        _mockHandler.SetCustomResponse(HttpStatusCode.OK, mockResponseJson);

        var request = new GenerateMealPlanRequest
        {
            Cuisines = ["Italian"],
            AvoidIngredients = ["peanuts"],
            DaysCount = 3,
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
        var result = await _client.GenerateMealPlanAsync(request);

        // Assert
        result.Should().NotBeNull();
        result.MealPlanId.Should().Be("plan-123");
        result.Meals.Should().HaveCount(1);
        result.Meals[0].RecipeTitle.Should().Be("Lemon Chicken");
        result.Meals[0].Ingredients.Should().HaveCount(1);
        result.Meals[0].Ingredients[0].DealPrice.Should().Be(2.99m);
        result.MissingPrimaryIngredients.Should().HaveCount(1);
        result.MissingPrimaryIngredients[0].IngredientName.Should().Be("Olive Oil");

        _mockHandler.CapturedRequests.Should().HaveCount(1);
        var captured = _mockHandler.CapturedRequests[0];
        captured.Method.Should().Be(HttpMethod.Post);
        captured.RequestUri!.ToString().Should().Be("http://localhost:8002/v1/planner/generate");
    }

    [Fact]
    public async Task GenerateMealPlanAsync_CorrectlyDeserializesMealsAndIngredients_MatchingFixture()
    {
        // Arrange - use default MockHttpMessageHandler response for v1/planner/generate
        var request = new GenerateMealPlanRequest
        {
            Cuisines = ["Mexican", "American"],
            DaysCount = 3
        };

        // Act
        var result = await _client.GenerateMealPlanAsync(request);

        // Assert
        result.Should().NotBeNull();
        result.MealPlanId.Should().Be("plan-draft-20260908-001");
        result.Meals.Should().NotBeEmpty();

        var firstMeal = result.Meals[0];
        firstMeal.RecipeTitle.Should().Be("Lemon Pepper Chicken");
        firstMeal.MealType.Should().Be("Dinner");
        firstMeal.Instructions.Should().NotBeEmpty();
        firstMeal.Ingredients.Should().NotBeEmpty();

        var chickenIngredient = firstMeal.Ingredients.FirstOrDefault(i => i.Name == "Boneless Skinless Chicken Breast");
        chickenIngredient.Should().NotBeNull();
        chickenIngredient!.Quantity.Should().Be(1.5m);
        chickenIngredient.Unit.Should().Be("lbs");
        chickenIngredient.DealId.Should().Be("deal-chicken-breast-001");
        chickenIngredient.StoreName.Should().Be("Ralphs");
        chickenIngredient.DealPrice.Should().Be(2.99m);

        result.MissingPrimaryIngredients.Should().NotBeEmpty();
        var missingBeef = result.MissingPrimaryIngredients.FirstOrDefault(m => m.IngredientName.StartsWith("Ground Beef"));
        missingBeef.Should().NotBeNull();
        missingBeef!.Quantity.Should().Be(1.0m);
        missingBeef.AssociatedRecipeTitles.Should().Contain("Street Tacos");
    }

    [Fact]
    public async Task GenerateMealPlanAsync_ThrowsPlanningDomainException_On500ServerError()
    {
        // Arrange
        _mockHandler.SetServerError("LLM Planning service failed unexpectedly");

        var request = new GenerateMealPlanRequest
        {
            Cuisines = ["Mexican"],
            DaysCount = 3
        };

        // Act
        var act = () => _client.GenerateMealPlanAsync(request);

        // Assert
        var exception = await act.Should().ThrowAsync<PlanningDomainException>();
        exception.Which.StatusCode.Should().Be(HttpStatusCode.InternalServerError);
        exception.Which.ResponseBody.Should().Contain("LLM Planning service failed unexpectedly");
    }

    [Fact]
    public async Task GenerateMealPlanAsync_ThrowsPlanningDomainException_On503ServiceUnavailable()
    {
        // Arrange
        _mockHandler.SetCustomResponse(HttpStatusCode.ServiceUnavailable, "Planning service temporarily overloaded");

        var request = new GenerateMealPlanRequest
        {
            Cuisines = ["Italian"],
            DaysCount = 3
        };

        // Act
        var act = () => _client.GenerateMealPlanAsync(request);

        // Assert
        var exception = await act.Should().ThrowAsync<PlanningDomainException>();
        exception.Which.StatusCode.Should().Be(HttpStatusCode.ServiceUnavailable);
        exception.Which.ResponseBody.Should().Be("Planning service temporarily overloaded");
    }

    [Fact]
    public async Task GenerateMealPlanAsync_ThrowsPlanningDomainException_On400BadRequest()
    {
        // Arrange
        _mockHandler.SetCustomResponse(HttpStatusCode.BadRequest, "Invalid request payload");

        var request = new GenerateMealPlanRequest
        {
            DaysCount = -1
        };

        // Act
        var act = () => _client.GenerateMealPlanAsync(request);

        // Assert
        var exception = await act.Should().ThrowAsync<PlanningDomainException>();
        exception.Which.StatusCode.Should().Be(HttpStatusCode.BadRequest);
        exception.Which.ResponseBody.Should().Be("Invalid request payload");
    }

    [Fact]
    public async Task GenerateMealPlanAsync_ThrowsArgumentNullException_WhenRequestIsNull()
    {
        // Act
        var act = () => _client.GenerateMealPlanAsync(null!);

        // Assert
        await act.Should().ThrowAsync<ArgumentNullException>();
    }
}
