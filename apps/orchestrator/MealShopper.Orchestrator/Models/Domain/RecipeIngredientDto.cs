using System.Text.Json;
using System.Text.Json.Serialization;

namespace MealShopper.Orchestrator.Models.Domain;

public class RecipeIngredientDto
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;

    [JsonPropertyName("quantity")]
    [JsonConverter(typeof(QuantityStringConverter))]
    public string Quantity { get; set; } = string.Empty;

    [JsonPropertyName("is_promotional")]
    public bool IsPromotional { get; set; }

    [JsonPropertyName("deal_id")]
    public string? DealId { get; set; }

    [JsonPropertyName("store_name")]
    public string? StoreName { get; set; }
}

public class QuantityStringConverter : JsonConverter<string>
{
    public override string Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
    {
        if (reader.TokenType == JsonTokenType.Number)
        {
            if (reader.TryGetDecimal(out var dec))
            {
                return dec.ToString(System.Globalization.CultureInfo.InvariantCulture);
            }
            if (reader.TryGetInt64(out var l))
            {
                return l.ToString(System.Globalization.CultureInfo.InvariantCulture);
            }
            if (reader.TryGetDouble(out var dbl))
            {
                return dbl.ToString(System.Globalization.CultureInfo.InvariantCulture);
            }
        }
        return reader.GetString() ?? string.Empty;
    }

    public override void Write(Utf8JsonWriter writer, string value, JsonSerializerOptions options)
    {
        writer.WriteStringValue(value);
    }
}
