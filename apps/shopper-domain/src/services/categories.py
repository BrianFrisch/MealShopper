import re
from typing import Any, Dict, List, Literal, Optional

# Standard normalized grocery categories
VALID_CATEGORIES: List[str] = [
    "Produce",
    "Meat",
    "Seafood",
    "Dairy",
    "Bakery",
    "Pantry",
]

NormalizedCategory = Literal[
    "Produce",
    "Meat",
    "Seafood",
    "Dairy",
    "Bakery",
    "Pantry",
]

CATEGORY_MAP: Dict[str, NormalizedCategory] = {
    "produce": "Produce",
    "fruits": "Produce",
    "fruit": "Produce",
    "vegetables": "Produce",
    "vegetable": "Produce",
    "fresh produce": "Produce",
    "meat & poultry": "Meat",
    "meat and poultry": "Meat",
    "meat": "Meat",
    "fresh meat": "Meat",
    "poultry": "Meat",
    "beef": "Meat",
    "chicken": "Meat",
    "pork": "Meat",
    "turkey": "Meat",
    "lamb": "Meat",
    "seafood": "Seafood",
    "fresh seafood": "Seafood",
    "fish": "Seafood",
    "shellfish": "Seafood",
    "dairy & eggs": "Dairy",
    "dairy and eggs": "Dairy",
    "dairy": "Dairy",
    "eggs": "Dairy",
    "milk": "Dairy",
    "cheese": "Dairy",
    "pantry": "Pantry",
    "grocery": "Pantry",
    "snacks": "Pantry",
    "condiments": "Pantry",
    "canned goods": "Pantry",
    "bakery": "Bakery",
    "bread": "Bakery",
    "baked goods": "Bakery",
    "frozen": "Pantry",
    "frozen foods": "Pantry",
    "frozen meals": "Pantry",
    "beverages": "Pantry",
    "beverage": "Pantry",
    "drinks": "Pantry",
    "soda": "Pantry",
    "aldi finds": "Pantry",
}

DEFAULT_CATEGORY_MAP: Dict[str, str] = dict(CATEGORY_MAP)

PRIMARY_CATEGORIES = {
    "meat",
    "fresh meat",
    "poultry",
    "beef",
    "pork",
    "chicken",
    "meat & poultry",
    "meat and poultry",
    "seafood",
    "fresh seafood",
    "fish",
    "shellfish",
}

NON_PRIMARY_MEAT_TERMS: tuple[str, ...] = (
    "lunch meat",
    "lunchmeat",
    "lunchmeats",
    "deli meat",
    "deli meats",
    "frank",
    "franks",
    "hot dog",
    "hot dogs",
    "bologna",
    "lunchables",
    "coffee",
    "roaster",
)

NON_PRIMARY_ITEM_TERMS = NON_PRIMARY_MEAT_TERMS

ALDI_FINDS_TERMS: tuple[str, ...] = (
    "aldi find",
    "aldi finds",
    "weekly find",
    "weekly finds",
    "special buy",
    "limited time",
    "while supplies last",
)

PANTRY_TERMS: tuple[str, ...] = (
    "pizza",
    "hot pocket",
    "hot pockets",
    "burrito",
    "chimichanga",
    "lasagna",
    "meal kit",
    "tv dinner",
    "bites",
    "waffles",
    "ice cream",
    "chips",
    "candy",
    "cookies",
    "crackers",
    "cereal",
    "tortillas",
    "buns",
    "bread",
    "dressing",
    "sauce",
    "mustard",
    "mayo",
    "beverage",
    "soda",
    "beer",
    "wine",
    "tequila",
    "whiskey",
    "vodka",
    "wipes",
    "charcoal",
    "pillow",
    "bucket",
    "tissue",
    "toothpaste",
    "shampoo",
    *NON_PRIMARY_MEAT_TERMS,
)

MEAT_TERMS: tuple[str, ...] = (
    "fresh meat special",
    "fresh meat",
    "weekly fresh",
    "meat special",
    "meat",
    "poultry",
    "beef",
    "pork",
    "chicken",
    "turkey",
    "steak",
    "steaks",
    "lamb",
    "ribs",
    "spareribs",
    "sausage",
    "bratwurst",
    "bacon",
    "roast",
    "roasts",
    "chop",
    "chops",
    "pork loin",
    "drumstick",
    "drumsticks",
    "wing",
    "wings",
    "tri-tip",
    "tri tip",
    "flanken",
    "ribeye",
    "sirloin",
    "chuck roast",
    "tenderloin",
    "brisket",
    "patties",
    "ground beef",
)

SEAFOOD_TERMS: tuple[str, ...] = (
    "seafood",
    "fresh seafood",
    "fish",
    "shrimp",
    "salmon",
    "tilapia",
    "tuna",
    "crab",
    "lobster",
    "cod",
    "flounder",
    "scallop",
    "scallops",
    "trout",
    "halibut",
    "mahi",
    "rockfish",
    "catfish",
    "swai",
    "camarón",
    "camaron",
    "mojarra",
    "jaiba",
    "bagre",
)

PRODUCE_TERMS: tuple[str, ...] = (
    "produce",
    "fresh fruit",
    "fresh vegetable",
    "fruit",
    "fruits",
    "vegetable",
    "vegetables",
    "greens",
    "apple",
    "apples",
    "banana",
    "bananas",
    "avocado",
    "avocados",
    "berry",
    "berries",
    "strawberry",
    "strawberries",
    "blueberry",
    "blueberries",
    "raspberry",
    "raspberries",
    "blackberry",
    "blackberries",
    "salad",
    "spinach",
    "lettuce",
    "kale",
    "tomato",
    "tomatoes",
    "potato",
    "potatoes",
    "onion",
    "onions",
    "carrot",
    "carrots",
    "pepper",
    "peppers",
    "bell pepper",
    "mushroom",
    "mushrooms",
    "cucumber",
    "cucumbers",
    "zucchini",
    "squash",
    "broccoli",
    "cauliflower",
    "asparagus",
    "celery",
    "citrus",
    "orange",
    "oranges",
    "lemon",
    "lemons",
    "lime",
    "limes",
    "corn",
    "peaches",
    "plums",
    "grape",
    "grapes",
    "watermelon",
    "cantaloupe",
    "honeydew",
    "pineapple",
    "mango",
    "mandarin",
    "mandarins",
    "clementines",
)

DAIRY_TERMS: tuple[str, ...] = (
    "dairy & eggs",
    "dairy",
    "cheese",
    "milk",
    "egg",
    "eggs",
    "yogurt",
    "butter",
    "cream",
    "heavy cream",
    "creamer",
    "cheddar",
    "mozzarella",
    "sour cream",
    "cottage cheese",
)

BAKERY_TERMS: tuple[str, ...] = (
    "bakery",
    "bread",
    "bagel",
    "bagels",
    "pastry",
    "muffin",
    "muffins",
    "croissant",
    "croissants",
    "cake",
    "rolls",
    "brioche",
)


def _contains_term(text: str, terms: List[str] | tuple[str, ...]) -> bool:
    for term in terms:
        if re.search(rf"\b{re.escape(term)}\b", text):
            return True
    return False


def normalize_category_label(value: Any) -> Any:
    """Normalizes a category string to one of VALID_CATEGORIES if recognized."""
    if isinstance(value, str):
        key = value.strip().lower()
        if key in CATEGORY_MAP:
            return CATEGORY_MAP[key]
        for cat in VALID_CATEGORIES:
            if cat.lower() == key:
                return cat
    return value


def normalize_category_key(category: str) -> str:
    """Normalizes category string to lowercase standard Redis index slug."""
    cat = (category or "").strip().lower()
    if cat in {"meat", "fresh meat", "meat & poultry", "meat and poultry", "poultry", "beef", "pork", "chicken", "turkey", "lamb"}:
        return "meat_and_poultry"
    if cat in {"seafood", "fresh seafood", "fish", "shellfish"}:
        return "seafood"
    if cat in {"produce", "fresh produce", "fruits", "fruit", "vegetables", "vegetable"}:
        return "produce"
    if cat in {"dairy", "dairy & eggs", "dairy and eggs", "milk", "cheese", "eggs"}:
        return "dairy_and_eggs"
    if cat in {"bakery", "bread", "baked goods"}:
        return "bakery"
    if cat in {"frozen", "frozen foods", "frozen meals"}:
        return "frozen"
    if cat in {"beverages", "drinks", "beverage", "soda"}:
        return "beverages"
    return "pantry"


def is_excluded_primary_meat_item(product_name: str) -> bool:
    """Returns True if an item name is lunch meat, franks/hot dogs, coffee, or cookware."""
    if not product_name:
        return False
    return _contains_term(product_name.lower(), NON_PRIMARY_MEAT_TERMS)


def is_primary_deal(deal: dict[str, Any]) -> bool:
    """Returns True if a deal belongs to the primary (Meat/Seafood) tier and is not an excluded item."""
    category = (
        deal.get("normalized_category")
        or deal.get("category")
        or ""
    ).strip().lower()
    if category not in PRIMARY_CATEGORIES:
        return False
    item_text = f"{deal.get('clean_name') or ''} {deal.get('item_name') or ''}".strip()
    if is_excluded_primary_meat_item(item_text):
        return False
    return True


def standardize_category(
    raw_category: str,
    product_name: str = "",
    category_map: Optional[Dict[str, str]] = None,
) -> str:
    """
    Maps raw category strings and product titles to standardized categories:
    Produce, Dairy, Meat, Seafood, Bakery, Pantry.
    """
    raw_clean = (raw_category or "").strip()
    item_clean = (product_name or "").lower()
    cat_lower = raw_clean.lower()
    combined = f"{cat_lower} {item_clean}"
    effective_map = category_map if category_map is not None else DEFAULT_CATEGORY_MAP

    # 1. Prepared / Convenience / Non-food / Lunch meat & franks -> Pantry
    if any(term in combined for term in PANTRY_TERMS):
        return "Pantry"

    # 2. Product-specific checks when category is combined/ambiguous (e.g. 'Meat & Seafood')
    if any(k in item_clean for k in MEAT_TERMS):
        return "Meat"
    if any(k in item_clean for k in SEAFOOD_TERMS):
        return "Seafood"

    # 3. Seafood checks on combined string
    if any(k in combined for k in SEAFOOD_TERMS):
        return "Seafood"

    # 4. Meat checks on combined string
    if any(k in combined for k in MEAT_TERMS):
        return "Meat"

    # 5. Produce checks
    if any(k in combined for k in PRODUCE_TERMS):
        return "Produce"

    # 6. Dairy checks
    if any(k in combined for k in DAIRY_TERMS):
        return "Dairy"

    # 7. Bakery checks
    if any(k in combined for k in BAKERY_TERMS):
        return "Bakery"

    # 8. Explicit category map fallback (excluding generic 'grocery')
    if cat_lower in effective_map and cat_lower != "grocery":
        return effective_map[cat_lower]

    return "Pantry"


def resolve_protein_subtype(product_name: str, normalized_category: str) -> Optional[str]:
    """Resolves specific protein subtype for meat/seafood deals."""
    if normalized_category not in ("Meat", "Seafood"):
        return None

    name = (product_name or "").lower()
    if normalized_category == "Seafood" or _contains_term(name, SEAFOOD_TERMS):
        return "Seafood"

    # 1. Explicit animal/species keywords first so cut words (e.g. 'roast', 'breast', 'sirloin')
    #    do not override explicit species (e.g. 'Turkey Roast', 'Pork Shoulder Roast', 'Lamb Loin Chops').
    if _contains_term(name, ["turkey", "turkeys", "pavo"]):
        return "Turkey"
    if _contains_term(name, ["lamb", "cordero"]):
        return "Lamb"
    if _contains_term(name, ["chicken", "chickens", "poultry", "pollo"]):
        return "Chicken"
    if _contains_term(
        name,
        [
            "beef", "res", "angus", "grass-fed", "grass fed", "stew meat",
            "ground beef", "carne asada", "birria",
        ],
    ):
        return "Beef"
    if _contains_term(
        name,
        [
            "pork", "puerco", "cerdo", "bacon", "ham", "hams", "sausage", "sausages",
            "bratwurst", "chorizo", "carnitas", "chilorio", "sparerib", "spareribs",
        ],
    ):
        return "Pork"

    # 2. Cut-based fallbacks when animal species is omitted
    if _contains_term(
        name,
        [
            "breast", "breasts", "thigh", "thighs", "wing", "wings",
            "drumstick", "drumsticks", "tender", "tenders", "leg quarter", "leg quarters",
        ],
    ):
        return "Chicken"
    if _contains_term(
        name,
        [
            "steak", "steaks", "roast", "roasts", "tri-tip", "tri tip", "chuck",
            "patties", "patty", "ribeye", "sirloin", "brisket", "flanken",
            "t-bone", "t bone", "porterhouse", "short rib", "short ribs",
        ],
    ):
        return "Beef"
    if _contains_term(name, ["ribs", "chop", "chops", "loin", "tenderloin", "tenderloins", "belly"]):
        return "Pork"

    return "Other"
