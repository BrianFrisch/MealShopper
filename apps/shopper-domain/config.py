import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DEALS_PATH = BASE_DIR / "data" / "deals.json"

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
SHOPPER_DATABASE_URL = os.getenv(
    "SHOPPER_DATABASE_URL",
    "postgresql://shopper_app:ShopperApp_Dev_Pwd99!@postgres:5432/mealshopper_shopper",
)
