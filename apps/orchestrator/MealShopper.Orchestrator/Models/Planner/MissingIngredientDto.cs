using System.Text.Json;
using System.Text.Json.Serialization;

namespace MealShopper.Orchestrator.Models.Planner;

/// <summary>
/// Represents a primary ingredient required by recipes that was not covered by available promotional deals.
/// </summary>
[JsonConverter(typeof(MissingIngredientDtoConverter))]
public class MissingIngredientDto
{
    [JsonPropertyName("ingredient_name")]
    public string IngredientName { get; set; } = string.Empty;

    [JsonPropertyName("quantity")]
    public decimal Quantity { get; set; }

    [JsonPropertyName("unit")]
    public string Unit { get; set; } = string.Empty;

    [JsonPropertyName("associated_recipe_titles")]
    public List<string> AssociatedRecipeTitles { get; set; } = [];

    public MissingIngredientDto() { }

    public MissingIngredientDto(string ingredientName)
    {
        IngredientName = ingredientName;
    }
}

public class MissingIngredientDtoConverter : JsonConverter<MissingIngredientDto>
{
    public override MissingIngredientDto Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
    {
        return reader.TokenType switch
        {
            JsonTokenType.String => new MissingIngredientDto(reader.GetString() ?? string.Empty),
            JsonTokenType.StartObject => ReadFromObject(ref reader),
            _ => new MissingIngredientDto()
        };
    }

    private static MissingIngredientDto ReadFromObject(ref Utf8JsonReader reader)
    {
        using var doc = JsonDocument.ParseValue(ref reader);
        var root = doc.RootElement;

        return new MissingIngredientDto
        {
            IngredientName = ExtractIngredientName(root),
            Quantity = ExtractQuantity(root),
            Unit = ExtractUnit(root),
            AssociatedRecipeTitles = ExtractAssociatedRecipeTitles(root)
        };
    }

    private static string ExtractIngredientName(JsonElement root)
    {
        if (root.TryGetProperty("ingredient_name", out var nameProp))
        {
            return nameProp.GetString() ?? string.Empty;
        }

        if (root.TryGetProperty("name", out var altName))
        {
            return altName.GetString() ?? string.Empty;
        }

        return string.Empty;
    }

    private static decimal ExtractQuantity(JsonElement root)
    {
        if (!root.TryGetProperty("quantity", out var qtyProp))
        {
            return 0m;
        }

        if (qtyProp.ValueKind == JsonValueKind.Number && qtyProp.TryGetDecimal(out var decVal))
        {
            return decVal;
        }

        if (qtyProp.ValueKind == JsonValueKind.String)
        {
            return TryParseQuantityString(qtyProp.GetString());
        }

        return 0m;
    }

    private static decimal TryParseQuantityString(string? text)
    {
        var match = System.Text.RegularExpressions.Regex.Match(text ?? string.Empty, @"^-?\d+(\.\d+)?");
        if (match.Success && decimal.TryParse(match.Value, System.Globalization.NumberStyles.Any, System.Globalization.CultureInfo.InvariantCulture, out var parsedDec))
        {
            return parsedDec;
        }

        return 0m;
    }

    private static string ExtractUnit(JsonElement root)
    {
        return root.TryGetProperty("unit", out var unitProp)
            ? unitProp.GetString() ?? string.Empty
            : string.Empty;
    }

    private static List<string> ExtractAssociatedRecipeTitles(JsonElement root)
    {
        if (root.TryGetProperty("associated_recipe_titles", out var recipesProp) && recipesProp.ValueKind == JsonValueKind.Array)
        {
            return recipesProp.EnumerateArray()
                .Select(e => e.GetString() ?? string.Empty)
                .Where(s => !string.IsNullOrWhiteSpace(s))
                .ToList();
        }

        return [];
    }

    public override void Write(Utf8JsonWriter writer, MissingIngredientDto value, JsonSerializerOptions options)
    {
        writer.WriteStartObject();
        writer.WriteString("ingredient_name", value.IngredientName);
        writer.WriteNumber("quantity", value.Quantity);
        writer.WriteString("unit", value.Unit);
        writer.WriteStartArray("associated_recipe_titles");
        foreach (var title in value.AssociatedRecipeTitles)
        {
            writer.WriteStringValue(title);
        }
        writer.WriteEndArray();
        writer.WriteEndObject();
    }
}