import os
import asyncpg #type: ignore
from typing import List, Any, Dict, Optional
from models import Store


EARTH_RADIUS_MILES = 3958.8
SHOPPER_DATABASE_URL = os.getenv(
    "SHOPPER_DATABASE_URL",
    "postgresql://shopper_app:ShopperApp_Dev_Pwd99!@postgres:5432/mealshopper_shopper",
)


class StoreRepository:
    def __init__(self, db_url: str = SHOPPER_DATABASE_URL):
        self.db_url = db_url

    @staticmethod
    def _row_to_store(record: Any) -> Store:
        r: Dict[str, Any] = dict(record) if not isinstance(record, dict) else record
        return Store(
            id=str(r.get("store_id") or ""),
            name=str(r.get("store_name") or r.get("display_name") or r.get("chain_name") or ""),
            street=str(r.get("street_address") or ""),
            city=str(r.get("city") or ""),
            state=str(r.get("state_province") or ""),
            zip_code=str(r.get("postal_code") or ""),
            latitude=float(r.get("latitude") or 0.0),
            longitude=float(r.get("longitude") or 0.0),
            distance_miles=float(r["distance_miles"]) if r.get("distance_miles") is not None else None,
            chain_id=str(r["chain_id"]) if r.get("chain_id") else None,
            adapter_name=str(r["adapter_name"]) if r.get("adapter_name") else None,
        )

    async def find_nearby(
        self,
        latitude: float,
        longitude: float,
        radius_miles: float = 10.0,
        max_stores: int = 15,
    ) -> List[Store]:
        conn = await asyncpg.connect(self.db_url)
        try:
            records = await conn.fetch(
                "SELECT * FROM fn_find_nearby_stores($1, $2, $3, $4);",
                longitude,
                latitude,
                float(radius_miles),
                int(max_stores),
            )
            return [self._row_to_store(record) for record in records]
        finally:
            await conn.close()

    async def get_store_context(self, store_id: str) -> Optional[Store]:
        conn = None
        try:
            conn = await asyncpg.connect(self.db_url, timeout=3)
            row = await conn.fetchrow(
                "SELECT * FROM fn_get_store_context($1);",
                store_id
            )
            return self._row_to_store(row) if row else None
        except Exception:
            return None
        finally:
            if conn is not None:
                await conn.close()