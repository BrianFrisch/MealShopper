using System.Net;
using System.Text;

namespace MealShopper.Orchestrator.Tests.Helpers;

/// <summary>
/// Mock HTTP message handler for testing HTTP clients interacting with external domain services.
/// </summary>
public class MockHttpMessageHandler : HttpMessageHandler
{
    private const string DefaultStoresResponse = """
    {
      "stores": [
        { "store_id": "store_vons_1", "name": "Vons", "address": "123 Hawthorne Blvd", "distance_miles": 1.5 },
        { "store_id": "store_grocoutlet_1", "name": "Grocery Outlet", "address": "456 Inglewood Ave", "distance_miles": 2.2 }
      ]
    }
    """;

    private const string FallbackTopDealsResponse = """
    {
      "timestamp": "2026-09-08T10:00:00Z",
      "region_context": {
        "coordinates": {
          "latitude": 34.053625,
          "longitude": -118.243007
        },
        "store_ids": [
          "store-ralphs-101",
          "store-traderjoes-204",
          "store-sprouts-305"
        ]
      },
      "deals": [
        {
          "deal_id": "deal-chicken-breast-001",
          "store_id": "store-ralphs-101",
          "store_name": "Ralphs",
          "item_name": "Boneless Skinless Chicken Breast",
          "normalized_category": "Meat",
          "deal_price": 2.99,
          "original_price": 4.99,
          "currency": "USD",
          "unit": "lb",
          "value_score": 9.2
        },
        {
          "deal_id": "deal-bell-peppers-002",
          "store_id": "store-sprouts-305",
          "store_name": "Sprouts Farmers Market",
          "item_name": "Organic Red Bell Peppers",
          "normalized_category": "Produce",
          "original_price": 1.99,
          "currency": "USD",
          "unit": "each",
          "value_score": 8.5
        },
        {
          "deal_id": "deal-tortillas-003",
          "store_id": "store-traderjoes-204",
          "store_name": "Trader Joe's",
          "item_name": "Corn Tortillas (12 count)",
          "normalized_category": "Bakery",
          "deal_price": 1.49,
          "original_price": 2.29,
          "currency": "USD",
          "unit": "count",
          "value_score": 7.8
        }
      ]
    }
    """;

    /// <summary>
    /// When set to true, forces a 500 Internal Server Error response for all incoming requests.
    /// </summary>
    public bool SimulateServerError { get; set; }

    /// <summary>
    /// Custom status code to override responses.
    /// </summary>
    public HttpStatusCode? StatusCodeOverride { get; set; }

    /// <summary>
    /// Custom response body to return when overridden.
    /// </summary>
    public string? ResponseBodyOverride { get; set; }

    /// <summary>
    /// Optional custom handler function to dynamically handle requests.
    /// </summary>
    public Func<HttpRequestMessage, HttpResponseMessage?>? CustomHandler { get; set; }

    /// <summary>
    /// List of captured requests intercepted by this handler.
    /// </summary>
    public List<HttpRequestMessage> CapturedRequests { get; } = new();

    /// <summary>
    /// Simulates a 500 Internal Server Error response.
    /// </summary>
    /// <param name="errorMessage">Optional error message body.</param>
    public void SetServerError(string errorMessage = "Internal Server Error")
    {
        SimulateServerError = true;
        StatusCodeOverride = HttpStatusCode.InternalServerError;
        ResponseBodyOverride = errorMessage;
    }

    /// <summary>
    /// Configures a custom response for testing.
    /// </summary>
    /// <param name="statusCode">HTTP status code.</param>
    /// <param name="responseBody">Response body content.</param>
    public void SetCustomResponse(HttpStatusCode statusCode, string responseBody)
    {
        StatusCodeOverride = statusCode;
        ResponseBodyOverride = responseBody;
    }

    /// <summary>
    /// Resets all overrides and captured requests.
    /// </summary>
    public void Reset()
    {
        SimulateServerError = false;
        StatusCodeOverride = null;
        ResponseBodyOverride = null;
        CustomHandler = null;
        CapturedRequests.Clear();
    }

    protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
    {
        CapturedRequests.Add(request);

        if (SimulateServerError)
        {
            var errorResponse = new HttpResponseMessage(HttpStatusCode.InternalServerError)
            {
                Content = new StringContent(ResponseBodyOverride ?? "Internal Server Error", Encoding.UTF8, "application/json")
            };
            return Task.FromResult(errorResponse);
        }

        if (StatusCodeOverride.HasValue)
        {
            var customResponse = new HttpResponseMessage(StatusCodeOverride.Value)
            {
                Content = new StringContent(ResponseBodyOverride ?? string.Empty, Encoding.UTF8, "application/json")
            };
            return Task.FromResult(customResponse);
        }

        if (CustomHandler != null)
        {
            var handlerResult = CustomHandler(request);
            if (handlerResult != null)
            {
                return Task.FromResult(handlerResult);
            }
        }

        var url = request.RequestUri?.ToString() ?? string.Empty;

        if (url.Contains("v1/shopper/stores", StringComparison.OrdinalIgnoreCase))
        {
            var response = new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent(DefaultStoresResponse, Encoding.UTF8, "application/json")
            };
            return Task.FromResult(response);
        }

        if (url.Contains("v1/shopper/deals", StringComparison.OrdinalIgnoreCase))
        {
            string dealsJson;
            var fixturePath = ResolveFixturePath("valid-top-deals.json");

            if (File.Exists(fixturePath))
            {
                dealsJson = File.ReadAllText(fixturePath);
            }
            else
            {
                dealsJson = FallbackTopDealsResponse;
            }

            var response = new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent(dealsJson, Encoding.UTF8, "application/json")
            };
            return Task.FromResult(response);
        }

        if (url.Contains("v1/planner/generate", StringComparison.OrdinalIgnoreCase))
        {
            string mealPlanJson;
            var fixturePath = ResolveFixturePath("valid-meal-plan.json");

            if (File.Exists(fixturePath))
            {
                mealPlanJson = File.ReadAllText(fixturePath);
            }
            else
            {
                mealPlanJson = """
                {
                  "meal_plan_id": "plan-draft-20260908-001",
                  "meals": [
                    {
                      "meal_type": "Dinner",
                      "recipe_title": "Lemon Pepper Chicken",
                      "description": "Crispy pan-seared lemon pepper chicken.",
                      "instructions": ["Sear chicken", "Add lemon"],
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
                  "missing_primary_ingredients": []
                }
                """;
            }

            var response = new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent(mealPlanJson, Encoding.UTF8, "application/json")
            };
            return Task.FromResult(response);
        }

        return Task.FromResult(new HttpResponseMessage(HttpStatusCode.NotFound)
        {
            Content = new StringContent("Not Found", Encoding.UTF8, "text/plain")
        });
    }

    private static string ResolveFixturePath(string fixtureFileName)
    {
        var currentDir = new DirectoryInfo(AppContext.BaseDirectory);
        while (currentDir != null && !Directory.Exists(Path.Combine(currentDir.FullName, "libs")))
        {
            currentDir = currentDir.Parent;
        }

        if (currentDir != null)
        {
            var resolved = Path.Combine(currentDir.FullName, "libs", "contracts", "tests", "fixtures", fixtureFileName);
            if (File.Exists(resolved))
            {
                return resolved;
            }
        }

        return Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "libs", "contracts", "tests", "fixtures", fixtureFileName));
    }
}
