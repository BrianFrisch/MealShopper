# apps/shopper-domain/src/services/grocery_chain_service.py
import logging
import os
from typing import Any, Dict, List, Optional, cast

try:
    import asyncpg  # type: ignore
except ImportError:
    asyncpg = None

logger = logging.getLogger(__name__)

SHOPPER_DATABASE_URL = os.getenv(
    "SHOPPER_DATABASE_URL",
    "postgresql://shopper_app:ShopperApp_Dev_Pwd99!@postgres:5432/mealshopper_shopper",
)


class GroceryChainService:
    """
    Service responsible for grocery chain metadata retrieval and modifications.
    """

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or SHOPPER_DATABASE_URL

    async def get_chain_metadata(self, chain_id: str) -> Dict[str, str]:
        """Retrieve grocery chain metadata from the database for a specific chain."""
        chain_key = chain_id.strip().lower()
        conn = await asyncpg.connect(self.db_url)
        try:
            row: Any = await conn.fetchrow(
                "SELECT chain_id, display_name, adapter_name, spider_name, flyer_source_type "
                "FROM fn_get_grocery_chains($1);",
                chain_key,
            )
            if not row:
                raise ValueError(f"Unsupported chain: {chain_id}")
            chain_value = cast(str, row["chain_id"])
            spider_value = cast(Optional[str], row["spider_name"])
            flyer_source_value = cast(Optional[str], row["flyer_source_type"])
            spider = spider_value or chain_value
            return {
                "chain_id": chain_value,
                "display_name": cast(str, row["display_name"]),
                "adapter_name": cast(str, row["adapter_name"]),
                "spider": spider,
                "spider_name": spider,
                "flyer_source_type": flyer_source_value or "flipp",
            }
        finally:
            await conn.close()

    async def get_all_chains(self) -> List[Dict[str, Any]]:
        """Retrieve all active grocery chains from the database."""
        conn = None
        try:
            conn = await asyncpg.connect(self.db_url, timeout=3)
            rows: Any = await conn.fetch(
                "SELECT chain_id, display_name, adapter_name, spider_name, flyer_source_type, is_active "
                "FROM fn_get_grocery_chains(NULL);"
            )
            chains: List[Dict[str, Any]] = []
            for row in rows:
                chain_value = cast(str, row["chain_id"])
                adapter_value = cast(str, row["adapter_name"])
                spider_value = cast(Optional[str], row["spider_name"])
                flyer_source_value = cast(Optional[str], row["flyer_source_type"])
                active_value = cast(Optional[bool], row.get("is_active", True))
                spider = spider_value or chain_value
                chains.append({
                    "chain_id": chain_value,
                    "display_name": cast(str, row["display_name"]),
                    "adapter_name": adapter_value,
                    "spider": spider,
                    "spider_name": spider,
                    "flyer_source_type": flyer_source_value or "flipp",
                    "is_active": active_value if active_value is not None else True,
                })
            return chains
        except Exception as exc:
            logger.warning("Failed to fetch all chains from database: %s", exc)
            return []
        finally:
            if conn is not None:
                await conn.close()

    async def upsert_chain(
        self,
        chain_id: str,
        display_name: str,
        adapter_name: str,
        spider_name: Optional[str] = None,
        flyer_source_type: str = "flipp",
    ) -> None:
        """Upsert grocery chain definition into the database."""
        conn = await asyncpg.connect(self.db_url)
        try:
            await conn.execute(
                "CALL sp_upsert_grocery_chain($1, $2, $3, $4, $5);",
                chain_id.strip().lower(),
                display_name,
                adapter_name,
                spider_name,
                flyer_source_type,
            )
        finally:
            await conn.close()
