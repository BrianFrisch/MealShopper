import json
import sys
from pathlib import Path
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

CURRENT_DIR = Path(__file__).resolve().parent
CONTRACTS_DIR = CURRENT_DIR.parent
FIXTURES_DIR = CURRENT_DIR / "fixtures"

SCHEMAS = {
    "top-deals": CONTRACTS_DIR / "top-deals.schema.json",
    "meal-plan": CONTRACTS_DIR / "meal-plan-draft.schema.json",
}

FIXTURE_PAIRS = [
    {
        "name": "Top Deals - Valid Fixture",
        "schema_key": "top-deals",
        "fixture_path": FIXTURES_DIR / "valid-top-deals.json",
        "expect_valid": True,
    },
    {
        "name": "Top Deals - Invalid Fixture",
        "schema_key": "top-deals",
        "fixture_path": FIXTURES_DIR / "invalid-top-deals.json",
        "expect_valid": False,
    },
    {
        "name": "Meal Plan Draft - Valid Fixture",
        "schema_key": "meal-plan",
        "fixture_path": FIXTURES_DIR / "valid-meal-plan.json",
        "expect_valid": True,
    },
    {
        "name": "Meal Plan Draft - Invalid Fixture",
        "schema_key": "meal-plan",
        "fixture_path": FIXTURES_DIR / "invalid-meal-plan.json",
        "expect_valid": False,
    },
]


def load_json(file_path: Path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_validations() -> bool:
    print("=" * 60)
    print("Starting JSON Schema Validation Suite (Draft 2020-12)")
    print(f"Contracts Directory: {CONTRACTS_DIR}")
    print(f"Fixtures Directory:  {FIXTURES_DIR}")
    print("=" * 60)

    validators = {}
    for key, schema_path in SCHEMAS.items():
        if not schema_path.exists():
            print(f"[ERROR] Schema file not found: {schema_path}")
            return False
        schema_json = load_json(schema_path)
        Draft202012Validator.check_schema(schema_json)
        validators[key] = Draft202012Validator(schema_json)

    all_passed = True

    for item in FIXTURE_PAIRS:
        test_name = item["name"]
        schema_key = item["schema_key"]
        fixture_path = item["fixture_path"]
        expect_valid = item["expect_valid"]

        if not fixture_path.exists():
            print(f"[FAIL] {test_name}: Fixture file not found at {fixture_path}")
            all_passed = False
            continue

        validator = validators[schema_key]
        fixture_data = load_json(fixture_path)

        errors = list(validator.iter_errors(fixture_data))

        if expect_valid:
            if not errors:
                print(f"[PASS] {test_name}: Conforms to {SCHEMAS[schema_key].name}")
            else:
                all_passed = False
                print(f"[FAIL] {test_name}: Expected valid payload, but got {len(errors)} error(s):")
                for err in errors:
                    path = " -> ".join(str(p) for p in err.absolute_path) or "(root)"
                    print(f"       - At '{path}': {err.message}")
        else:
            if errors:
                print(f"[PASS] {test_name}: Correctly rejected as invalid with {len(errors)} error(s):")
                for err in errors:
                    path = " -> ".join(str(p) for p in err.absolute_path) or "(root)"
                    print(f"       - Detected violation at '{path}': {err.message}")
            else:
                all_passed = False
                print(f"[FAIL] {test_name}: Expected validation errors, but fixture passed unexpectedly.")

    print("=" * 60)
    if all_passed:
        print("All schema validation checks passed successfully!")
    else:
        print("Some schema validation checks failed.")
    print("=" * 60)

    return all_passed


if __name__ == "__main__":
    success = run_validations()
    sys.exit(0 if success else 1)
