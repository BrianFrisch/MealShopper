import os
from urllib.parse import quote_plus


def _database_url() -> str:
    configured_url = os.getenv("PLANNER_DATABASE_URL")
    if configured_url:
        return configured_url

    host = os.getenv("PLANNER_DB_HOST")
    if host:
        username = quote_plus(os.getenv("PLANNER_DB_USER", "planner_app"))
        password = quote_plus(os.getenv("PLANNER_DB_PASSWORD", ""))
        port = os.getenv("PLANNER_DB_PORT", "5432")
        database = os.getenv("PLANNER_DB_NAME", "mealshopper_planner")
        return f"postgresql://{username}:{password}@{host}:{port}/{database}"

    return os.getenv(
        "PLANNER_DATABASE_URL",
        "postgresql://planner_app@localhost:5432/mealshopper_planner",
    )


PLANNER_DATABASE_URL = _database_url()
