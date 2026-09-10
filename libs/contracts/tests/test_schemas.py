import json
from pathlib import Path
import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

CURRENT_DIR = Path(__file__).resolve().parent
CONTRACTS_DIR = CURRENT_DIR.parent
FIXTURES_DIR = CURRENT_DIR / "fixtures"


def load_json(file_path: Path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def top_deals_validator() -> Draft202012Validator:
    schema_path = CONTRACTS_DIR / "top-deals.schema.json"
    schema_json = load_json(schema_path)
    Draft202012Validator.check_schema(schema_json)
    return Draft202012Validator(schema_json)


@pytest.fixture(scope="session")
def meal_plan_validator() -> Draft202012Validator:
    schema_path = CONTRACTS_DIR / "meal-plan-draft.schema.json"
    schema_json = load_json(schema_path)
    Draft202012Validator.check_schema(schema_json)
    return Draft202012Validator(schema_json)


class TestTopDealsSchema:
    def test_valid_top_deals(self, top_deals_validator: Draft202012Validator):
        fixture_path = FIXTURES_DIR / "valid-top-deals.json"
        data = load_json(fixture_path)
        # Should validate without raising ValidationError
        top_deals_validator.validate(data)

    def test_invalid_top_deals(self, top_deals_validator: Draft202012Validator):
        fixture_path = FIXTURES_DIR / "invalid-top-deals.json"
        data = load_json(fixture_path)
        with pytest.raises(ValidationError) as exc_info:
            top_deals_validator.validate(data)
        assert exc_info.value is not None


class TestMealPlanDraftSchema:
    def test_valid_meal_plan(self, meal_plan_validator: Draft202012Validator):
        fixture_path = FIXTURES_DIR / "valid-meal-plan.json"
        data = load_json(fixture_path)
        # Should validate without raising ValidationError
        meal_plan_validator.validate(data)

    def test_invalid_meal_plan(self, meal_plan_validator: Draft202012Validator):
        fixture_path = FIXTURES_DIR / "invalid-meal-plan.json"
        data = load_json(fixture_path)
        with pytest.raises(ValidationError) as exc_info:
            meal_plan_validator.validate(data)
        assert exc_info.value is not None
