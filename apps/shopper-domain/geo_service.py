import math
import os
import asyncpg #type: ignore
from typing import List, Any, Dict


EARTH_RADIUS_MILES = 3958.8
SHOPPER_DATABASE_URL = os.getenv(
    "SHOPPER_DATABASE_URL",
    "postgresql://shopper_app:ShopperApp_Dev_Pwd99!@postgres:5432/mealshopper_shopper",
)

def calculate_haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Calculates great-circle distance in miles between two coordinates."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(EARTH_RADIUS_MILES * c, 2)


class StoreRepository:
    def __init__(self, db_url: str = SHOPPER_DATABASE_URL):
        self.db_url = db_url

    async def find_nearby(
        self,
        latitude: float,
        longitude: float,
        radius_miles: float = 10.0,
        max_stores: int = 15,
    ) -> List[Dict[str, Any]]:
        conn = await asyncpg.connect(self.db_url)
        try:
            records = await conn.fetch(
                "SELECT * FROM fn_find_nearby_stores($1, $2, $3, $4);",
                longitude,
                latitude,
                float(radius_miles),
                int(max_stores),
            )
            return [dict(record) for record in records]
        finally:
            await conn.close()