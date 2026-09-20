import json
import math
from pathlib import Path
from typing import List
from models import Store

EARTH_RADIUS_MILES = 3958.8


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
    def __init__(self, data_path: Path):
        self._stores: List[Store] = []
        if data_path.exists():
            with open(data_path, "r", encoding="utf-8") as f:
                raw_stores = json.load(f)
                self._stores = [Store(**item) for item in raw_stores]

    def find_nearby(
        self, user_lat: float, user_lon: float, radius_miles: float, max_stores: int
    ) -> List[Store]:
        """Filters stores within radius_miles, sorts by closest, and caps by max_stores."""
        stores_with_distance: List[Store] = []

        for store in self._stores:
            distance = calculate_haversine_distance(
                user_lat, user_lon, store.latitude, store.longitude
            )
            if distance <= radius_miles:
                # Copy and attach calculated distance
                store_copy = store.model_copy(update={"distance_miles": distance})
                stores_with_distance.append(store_copy)

        # Sort ascending by distance and apply user's store cap
        stores_with_distance.sort(key=lambda s: s.distance_miles or 0.0)
        return stores_with_distance[:max_stores]