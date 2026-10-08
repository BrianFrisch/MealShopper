import os
import sys

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

try:
    from google import genai
except ImportError:
    print("Error: 'google-genai' package is not installed. Please install it using pip.", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable is not set.", file=sys.stderr)
        print("Please set GEMINI_API_KEY in your environment or .env file.", file=sys.stderr)
        sys.exit(1)

    print("Initializing Gemini client...")
    client = genai.Client(api_key=api_key)

    print("\nQuerying available models from Google GenAI...")
    try:
        models = list(client.models.list())
    except Exception as e:
        print(f"Error querying models: {e}", file=sys.stderr)
        sys.exit(1)

    gen_models = []
    for m in models:
        actions = getattr(m, "supported_actions", None) or []
        if "generateContent" in actions:
            gen_models.append(m)

    print(f"\nFound {len(gen_models)} models supporting 'generateContent':")
    print("-" * 80)
    for m in gen_models:
        name = getattr(m, "name", "N/A")
        display_name = getattr(m, "display_name", "N/A")
        actions = getattr(m, "supported_actions", [])
        print(f"• Model Name / ID:   {name}")
        print(f"  Display Name:      {display_name}")
        print(f"  Supported Methods: {', '.join(actions) if actions else 'N/A'}")
        print("-" * 80)

    test_model = "gemini-3.5-flash-lite"
    print(f"\nPerforming minimal test generation using '{test_model}'...")
    try:
        response = client.models.generate_content(
            model=test_model,
            contents="Say 'OK'",
        )
        output_text = response.text.strip() if hasattr(response, "text") and response.text else "No text response"
        print(f"Success! Model response: {output_text}")
    except Exception as e:
        print(f"Warning: Test generation failed for model '{test_model}': {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
