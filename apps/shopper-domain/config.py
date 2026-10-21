import os
from urllib.parse import quote_plus

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

if os.getenv("POSTGRES_HOST"):
    postgres_user = quote_plus(os.getenv("POSTGRES_USER", "shopper_app"))
    postgres_password = quote_plus(os.getenv("POSTGRES_PASSWORD", ""))
    postgres_host = os.environ["POSTGRES_HOST"]
    postgres_port = os.getenv("POSTGRES_PORT", "5432")
    postgres_database = os.getenv("POSTGRES_DB", "mealshopper_shopper")
    os.environ["SHOPPER_DATABASE_URL"] = (
        f"postgresql://{postgres_user}:{postgres_password}@"
        f"{postgres_host}:{postgres_port}/{postgres_database}"
    )
SHOPPER_DATABASE_URL = os.getenv(
    "SHOPPER_DATABASE_URL",
    "postgresql://shopper_app@localhost:5432/mealshopper_shopper",
)
