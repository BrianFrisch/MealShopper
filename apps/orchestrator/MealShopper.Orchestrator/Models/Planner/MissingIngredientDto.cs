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
        if (reader.TokenType == JsonTokenType.String)
        {
            return new MissingIngredientDto(reader.GetString() ?? string.Empty);
        }

        if (reader.TokenType == JsonTokenType.StartObject)
        {
            using var doc = JsonDocument.ParseValue(ref reader);
            var root = doc.RootElement;
            var dto = new MissingIngredientDto();

            if (root.TryGetProperty("ingredient_name", out var nameProp))
            {
                dto.IngredientName = nameProp.GetString() ?? string.Empty;
            }
            else if (root.TryGetProperty("name", out var altName))
            {
                dto.IngredientName = altName.GetString() ?? string.Empty;
            }

            if (root.TryGetProperty("quantity", out var qtyProp))
            {
                if (qtyProp.ValueKind == JsonValueKind.Number && qtyProp.TryGetDecimal(out var decVal))
                {
                    dto.Quantity = decVal;
                }
                else if (qtyProp.ValueKind == JsonValueKind.String)
                {
                    var text = qtyProp.GetString();
                    if (System.Text.RegularExpressions.Regex.Match(text ?? "", @"^-?\d+(\.\d+)?") is { Success: true } m)
                    {
                        if (decimal.TryParse(m.Value, out var parsedDec))
                        {
                            dto.Quantity = parsedDec;
                        }
                    }
                }
            }

            if (root.TryGetProperty("unit", out var unitProp))
            {
                dto.Unit = unitProp.GetString() ?? string.Empty;
            }

            if (root.TryGetProperty("associated_recipe_titles", out var recipesProp) && recipesProp.ValueKind == JsonValueKind.Array)
            {
                dto.AssociatedRecipeTitles = recipesProp.EnumerateArray()
                    .Select(e => e.GetString() ?? string.Empty)
                    .Where(s => !string.IsNullOrWhiteSpace(s))
                    .ToList();
            }

            return dto;
        }

        return new MissingIngredientDto();
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